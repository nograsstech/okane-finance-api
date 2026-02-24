import asyncio
import base64
import json
import logging
import math
import os
import warnings
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi import HTTPException
from starlette.status import HTTP_200_OK

# Suppress bokeh np.datetime64 timezone warning
warnings.filterwarnings(
    "ignore",
    message="no explicit representation of timezones available for np.datetime64",
    module="bokeh",
)

from app.db.postgres import AsyncSessionLocal
from app.db.repository import (
    BacktestStatRepository,
    TradeActionRepository,
    UniqueStrategyRepository,
)
from app.notification.service import send_trade_action_notification
from app.signals.strategies.calculate import calculate_signals, calculate_signals_async
from app.signals.strategies.perform_backtest import perform_backtest
from app.signals.utils.signals import get_all_signals, get_latest_signal
from app.signals.utils.yfinance import getYFinanceData, getYFinanceDataAsync

executor = ThreadPoolExecutor(max_workers=5)


def safe_float(value, default=0.0, decimals=3):
    """Safely convert a value to float, handling NaN and None values."""
    try:
        float_val = float(value)
        if math.isnan(float_val) or math.isinf(float_val):
            return default
        return round(float_val, decimals)
    except (TypeError, ValueError):
        return default


async def get_signals(ticker, interval, period, strategy, parameters, start=None, end=None):
    """Retrieves signals for a given ticker using the specified parameters."""
    try:
        df = None
        df1d = None
        try:
            df = await getYFinanceDataAsync(ticker, interval, period, start, end)
            if strategy == "macd_1":
                df1d = getYFinanceData(ticker, "1d", period, start, end)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to calculate signals. Error: {e}")

        signals_df = None
        try:
            signals_df = await calculate_signals_async(df, df1d, strategy, parameters)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to calculate signals. Error: {e}")
        current_signal = signals_df.iloc[-1]
        current_signal = json.loads(current_signal.to_json())

        latest_signal = get_latest_signal(signals_df)
        all_signals = get_all_signals(signals_df)

        return {
            "status": HTTP_200_OK,
            "message": "Signals",
            "data": {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "strategy": strategy,
                "signals": {
                    "latest_signal": latest_signal,
                    "all_signals": all_signals,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get signals. Error: {e}")


async def get_backtest_result(
    ticker,
    interval,
    period,
    strategy,
    parameters,
    start=None,
    end=None,
    strategy_id=None,
    backtest_process_uuid=None,
    notifications_on=False,
    skip_optimization=False,
    best_params=None,
):
    """
    Get the backtest result for a given ticker, interval, period, strategy, and parameters.

    The heavy CPU work (data fetch + backtest computation) runs in a thread pool
    via asyncio.to_thread() so it doesn't block the event loop.
    DB writes are done directly in the async portion.
    """
    print(f"\n--- BACKTEST BEGINS --\n--- Start backtest for {ticker} ---\n")
    print(f"Interval: {interval}")
    print(f"Period: {period}")
    print(f"Strategy: {strategy}")
    print(f"Parameters: {json.dumps(parameters, indent=4)}")
    if start:
        print(f"Start Date: {start}")
    if end:
        print(f"End Date: {end}")

    try:
        parameters_dict = json.loads(parameters) if parameters is not None else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse parameters. Error: {e}")

    # -----------------------------------------------------------------
    # Run CPU-bound work in a thread (doesn't block the event loop)
    # -----------------------------------------------------------------
    def _run_backtest():
        """Sync work: fetch data + compute backtest. Returns (bt, stats, trade_actions, strategy_parameters)."""
        df = getYFinanceData(ticker, interval, period, start, end)
        df1d = getYFinanceData(ticker, "1d", period, start, end) if strategy == "macd_1" else None

        signals_df = calculate_signals(df, df1d, strategy, parameters_dict)

        size = 0.01 if ticker == "BTC-USD" else 0.03

        return perform_backtest(
            signals_df,
            strategy,
            {
                "best": False,
                "size": size,
                "slcoef": 2.2,
                "tpslRatio": 2.0,
                "max_longs": parameters_dict.get("max_longs", 1),
                "max_shorts": parameters_dict.get("max_shorts", 1),
            },
            skip_optimization,
            best_params,
        )

    try:
        bt, stats, trade_actions, strategy_parameters = await asyncio.to_thread(_run_backtest)
        if bt is None or stats is None:
            raise HTTPException(
                status_code=400,
                detail="Backtest returned no results (strategy calculation may have failed or no trades were executed).",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to run backtest. Error: {e}")

    # Generate the HTML plot (also sync/CPU-bound)
    def _render_html():
        bt.plot(open_browser=False, filename="backtest.html")
        with open("backtest.html") as f:
            content = f.read()
        os.remove("backtest.html")
        return content

    html_content = await asyncio.to_thread(_render_html)
    logging.info("get_backtest_result finished")

    print("Original trade actions:", len(trade_actions))

    for ta in trade_actions:
        ta["backtest_id"] = strategy_id

    # -----------------------------------------------------------------
    # Persist results to DB (async — runs on the event loop directly)
    # -----------------------------------------------------------------
    result = await _persist_backtest_result(
        ticker=ticker,
        interval=interval,
        period=period,
        strategy=strategy,
        strategy_id=strategy_id,
        backtest_process_uuid=backtest_process_uuid,
        stats=stats,
        html_content=html_content,
        strategy_parameters=strategy_parameters,
        trade_actions=trade_actions,
        notifications_on=notifications_on,
    )

    notifications_on = result["notifications_on"]
    saved_trade_actions = result["trade_actions"]

    print("\n--- Sending trade action notifications ---\n")
    print(
        f"Notifications flag: {notifications_on}, Trade actions count: {len(saved_trade_actions)}"
    )
    if notifications_on and saved_trade_actions:
        print(f"Sending trade action notification for {len(saved_trade_actions)} actions...")
        try:
            send_trade_action_notification(
                strategy=strategy,
                ticker=ticker,
                interval=interval,
                trade_actions=saved_trade_actions,
            )
            print("Trade action notification sent successfully.")
        except ValueError as e:
            logging.error(f"Configuration error for notification: {e}")
            print(f"ERROR: Notification not configured - {e}")
        except Exception as e:
            logging.error(f"Failed to send notification. Error: {e}", exc_info=True)
            print(f"ERROR: Failed to send notification - {e}")
    else:
        if not notifications_on:
            print("Notifications disabled for this strategy (notifications_on=False).")
        if not saved_trade_actions:
            print("No trade actions to notify about.")

    print("\n--- COMPLETE ---\n")

    return {
        "status": HTTP_200_OK,
        "message": "Backtest results",
        "data": backtest_process_uuid,
    }


async def _persist_backtest_result(
    *,
    ticker: str,
    interval: str,
    period: str,
    strategy: str,
    strategy_id,
    backtest_process_uuid,
    stats,
    html_content: str,
    strategy_parameters: dict,
    trade_actions: list[dict],
    notifications_on: bool,
) -> dict:
    """Async DB writes for a completed backtest."""
    async with AsyncSessionLocal() as session:
        backtest_repo = BacktestStatRepository(session)
        trade_repo = TradeActionRepository(session)

        # Build backtest_stats payload
        backtest_stats_data: dict = {
            "ticker": ticker,
            "max_drawdown_percentage": round(float(stats["Max. Drawdown [%]"]), 3),
            "start_time": stats["Start"].strftime("%Y-%m-%d %H:%M:%S.%f"),
            "end_time": stats["End"].strftime("%Y-%m-%d %H:%M:%S.%f"),
            "duration": str(stats["Duration"]),
            "exposure_time_percentage": round(float(stats["Exposure Time [%]"]), 3),
            "final_equity": round(float(stats["Equity Final [$]"]), 3),
            "peak_equity": round(float(stats["Equity Peak [$]"]), 3),
            "return_percentage": round(float(stats["Return [%]"]), 3),
            "buy_and_hold_return": round(float(stats["Buy & Hold Return [%]"]), 3),
            "return_annualized": round(float(stats["Return (Ann.) [%]"]), 3),
            "volatility_annualized": round(float(stats["Volatility (Ann.) [%]"]), 3),
            "sharpe_ratio": round(float(stats["Sharpe Ratio"]), 3),
            "sortino_ratio": round(float(stats["Sortino Ratio"]), 3),
            "calmar_ratio": round(float(stats["Calmar Ratio"]), 3),
            "average_drawdown_percentage": round(float(stats["Avg. Drawdown [%]"]), 3),
            "max_drawdown_duration": str(stats["Max. Drawdown Duration"]),
            "average_drawdown_duration": str(stats["Avg. Drawdown Duration"]),
            "trade_count": stats["# Trades"],
            "win_rate": round(float(stats["Win Rate [%]"]), 3),
            "best_trade": round(float(stats["Best Trade [%]"]), 3),
            "worst_trade": round(float(stats["Worst Trade [%]"]), 3),
            "avg_trade": round(float(stats["Avg. Trade [%]"]), 3),
            "max_trade_duration": str(stats["Max. Trade Duration"]),
            "average_trade_duration": str(stats["Avg. Trade Duration"]),
            "profit_factor": round(float(stats["Profit Factor"]), 3),
            "html": html_content,
            "strategy": strategy,
            "period": period,
            "interval": interval,
            "ref_id": backtest_process_uuid,
            "updated_at": datetime.now(UTC),
            "last_optimized_at": datetime.now(UTC),
            "tpsl_ratio": (
                round(float(strategy_parameters.get("tpslRatio")), 3)
                if strategy_parameters.get("tpslRatio") not in [None, ""]
                else None
            ),
            "sl_coef": (
                round(float(strategy_parameters.get("slcoef")), 3)
                if strategy_parameters.get("slcoef") not in [None, ""]
                else None
            ),
            "tp_coef": (
                round(float(strategy_parameters.get("TPcoef")), 3)
                if strategy_parameters.get("TPcoef") not in [None, ""]
                else None
            ),
        }

        # Deflate HTML
        try:
            compressed = zlib.compress(html_content.encode("utf-8"), level=9)
            backtest_stats_data["html"] = base64.b64encode(compressed).decode("utf-8")
        except Exception as e:
            logging.error("Failed to deflate HTML: %s", e)

        # Upsert backtest_stats first to get the existing record (if any)
        updated_stat = None
        try:
            logging.info(
                "Saving backtest stats to DB. Ticker: %s. Strategy: %s. Strategy ID: %s",
                ticker,
                strategy,
                strategy_id,
            )
            updated_stat = await backtest_repo.upsert(backtest_stats_data)
        except Exception as e:
            logging.error("Failed to save backtest stats: %s", e)

        # Compute the metrics-based flag and persist it to the DB record.
        # NOTE: this does NOT override the `notifications_on` parameter that was
        # passed into this function — that value (from strategy.notifications_on)
        # is the authoritative source for whether to actually send a notification.
        # Only set notifications_on if the existing value is None (empty/initial).
        good_sharpe = backtest_stats_data["sharpe_ratio"] > 0
        good_return = backtest_stats_data["return_percentage"] > 0
        good_winrate = backtest_stats_data["win_rate"] > 60
        computed_notifications_on = (good_sharpe and good_return) or good_winrate

        # Check if there's an existing record with a notifications_on value
        existing_notifications_on = None
        if updated_stat and updated_stat.notifications_on is not None:
            existing_notifications_on = updated_stat.notifications_on

        # Only set notifications_on if it was previously None (empty/initial)
        if existing_notifications_on is None:
            backtest_stats_data["notifications_on"] = computed_notifications_on
            # Update the record again with the computed value
            try:
                updated_stat = await backtest_repo.upsert(backtest_stats_data)
            except Exception as e:
                logging.error("Failed to update notifications_on: %s", e)
        else:
            backtest_stats_data["notifications_on"] = existing_notifications_on

        print(
            f"Notifications — strategy flag: {notifications_on}, "
            f"computed flag: {computed_notifications_on}, "
            f"existing flag: {existing_notifications_on}, "
            f"final flag: {backtest_stats_data['notifications_on']} "
            f"(sharpe>0={good_sharpe}, return>0={good_return}, winrate>60={good_winrate})"
        )

        # Determine which trade actions are "new" by querying against the correct backtest_stat ID
        if updated_stat is not None:
            latest_ta = await trade_repo.get_latest_for_strategy(updated_stat.id)

            if latest_ta is not None:
                # Strip tzinfo from both sides so naive/aware mismatches never raise TypeError.
                # psycopg3 can return TIMESTAMP WITHOUT TIME ZONE as tz-aware in some configs.
                cutoff_dt = latest_ta.datetime
                if hasattr(cutoff_dt, "tzinfo") and cutoff_dt.tzinfo is not None:
                    cutoff_dt = cutoff_dt.replace(tzinfo=None)

                new_trade_actions = []
                for ta in trade_actions:
                    raw_dt = ta.get("datetime", "")
                    try:
                        ta_dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S.%f")
                    except (ValueError, TypeError):
                        try:
                            ta_dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError):
                            continue
                    passed = ta_dt > cutoff_dt
                    if passed:
                        new_trade_actions.append(ta)
                trade_actions = new_trade_actions
            else:
                trade_actions = trade_actions[-1:]

            for ta in trade_actions:
                ta["backtest_id"] = updated_stat.id

        else:
            logging.error("updated_stat is empty — backtest_id not set on trade actions")
            trade_actions = trade_actions[-1:]

        # Insert trade actions
        saved_trade_actions = []
        try:
            logging.info("Saving trade actions to DB. Ticker: %s", ticker)
            if trade_actions:
                saved_trade_actions = await trade_repo.insert_many(trade_actions)
                print(f"Trade actions saved to DB. Count: {len(saved_trade_actions)}")
            else:
                print("No new trade actions to save (all filtered by deduplication).")
        except Exception as e:
            logging.error("Failed to save trade actions: %s", e)

    return {
        "notifications_on": notifications_on,
        "trade_actions": saved_trade_actions,
    }


async def replay_backtest(backtest_id: int):
    """
    Replay a backtest from stored TradeAction records.

    Fetches historical data fresh from yfinance and applies the stored trades.
    No caching - calculates on the fly.

    Args:
        backtest_id: The ID of the backtest to replay

    Returns:
        dict with status, message, and data (backtest stats + HTML)
    """
    print(f"\n--- REPLAY BACKTEST ---\n--- Backtest ID: {backtest_id} ---\n")

    # Fetch backtest metadata and trade actions from DB
    async with AsyncSessionLocal() as session:
        backtest_repo = BacktestStatRepository(session)
        trade_repo = TradeActionRepository(session)

        # Get the BacktestStat
        backtest_stat = await backtest_repo.get_by_id(backtest_id)
        if backtest_stat is None:
            print(f"[REPLAY] Backtest with ID {backtest_id} not found")
            raise HTTPException(status_code=404, detail=f"Backtest with ID {backtest_id} not found")

        print(
            f"[REPLAY] Found backtest: {backtest_stat.ticker} {backtest_stat.strategy} {backtest_stat.interval}"
        )

        # Get all trade actions
        trade_actions = await trade_repo.get_all_for_backtest(backtest_id)
        if not trade_actions:
            print(f"[REPLAY] No trade actions found for backtest ID {backtest_id}")
            raise HTTPException(
                status_code=404, detail=f"No trade actions found for backtest ID {backtest_id}"
            )

        print(f"[REPLAY] Found {len(trade_actions)} trade actions in database")

        # Convert TradeAction ORM models to dicts for the strategy
        trade_schedule = []
        for ta in trade_actions:
            trade_schedule.append(
                {
                    "datetime": ta.datetime.strftime("%Y-%m-%d %H:%M:%S.%f")
                    if ta.datetime
                    else None,
                    "trade_action": ta.trade_action,
                    "entry_price": ta.entry_price,
                    "price": ta.price,
                    "sl": ta.sl,
                    "tp": ta.tp,
                    "size": ta.size,
                }
            )

    # Extract backtest parameters
    ticker = backtest_stat.ticker
    interval = backtest_stat.interval
    period = backtest_stat.period
    start_time = backtest_stat.start_time
    end_time = backtest_stat.end_time

    print(f"Replaying backtest for {ticker} from {start_time} to {end_time}")
    print(f"Found {len(trade_schedule)} trade actions to replay")

    # Validate required fields
    if not all([ticker, interval, period]):
        missing = []
        if not ticker:
            missing.append("ticker")
        if not interval:
            missing.append("interval")
        if not period:
            missing.append("period")
        print(f"[REPLAY] Missing required fields: {missing}")
        raise HTTPException(
            status_code=400, detail=f"Backtest is missing required fields: {', '.join(missing)}"
        )

    # -----------------------------------------------------------------
    # Run CPU-bound work in a thread (doesn't block the event loop)
    # -----------------------------------------------------------------
    def _run_replay():
        """Sync work: fetch data + compute backtest replay."""
        from app.signals.strategies.replay.predefined_trade_strategy import (
            backtest as replay_backtest_func,
        )

        # Fetch fresh historical data from yfinance
        print(f"[REPLAY] Fetching yfinance data for {ticker} {interval} {period}")
        df = getYFinanceData(
            ticker=ticker, interval=interval, period=period, start=start_time, end=end_time
        )

        if df is None or df.empty:
            raise ValueError(f"No data returned from yfinance for {ticker}")

        print(f"[REPLAY] Got yfinance data: shape={df.shape}")

        # Run the replay backtest
        return replay_backtest_func(df, trade_schedule)

    try:
        bt, stats, trade_actions, strategy_parameters = await asyncio.to_thread(_run_replay)
        if bt is None or stats is None:
            print("[REPLAY] Backtest returned None")
            raise HTTPException(
                status_code=400,
                detail="Backtest replay returned no results.",
            )
        print(f"[REPLAY] Backtest completed successfully")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REPLAY] Error during replay: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to replay backtest. Error: {e}")

    # Generate the HTML plot (also sync/CPU-bound)
    def _render_html():
        bt.plot(open_browser=False, filename="backtest_replay.html")
        with open("backtest_replay.html", "r", encoding="utf-8") as f:
            content = f.read()
        os.remove("backtest_replay.html")
        print(f"[REPLAY] HTML content length: {len(content)} characters")
        print(f"[REPLAY] HTML starts with: {content[:200]}")
        print(f"[REPLAY] HTML ends with: {content[-200:]}")
        return content

    html_content = await asyncio.to_thread(_render_html)
    logging.info("replay_backtest finished")

    # Build response DTO following existing pattern
    backtest_stats_data = {
        "ticker": ticker,
        "max_drawdown_percentage": safe_float(stats["Max. Drawdown [%]"]),
        "start_time": stats["Start"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "end_time": stats["End"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration": str(stats["Duration"]),
        "exposure_time_percentage": safe_float(stats["Exposure Time [%]"]),
        "final_equity": safe_float(stats["Equity Final [$]"]),
        "peak_equity": safe_float(stats["Equity Peak [$]"]),
        "return_percentage": safe_float(stats["Return [%]"]),
        "buy_and_hold_return": safe_float(stats["Buy & Hold Return [%]"]),
        "return_annualized": safe_float(stats["Return (Ann.) [%]"]),
        "volatility_annualized": safe_float(stats["Volatility (Ann.) [%]"]),
        "sharpe_ratio": safe_float(stats["Sharpe Ratio"]),
        "sortino_ratio": safe_float(stats["Sortino Ratio"]),
        "calmar_ratio": safe_float(stats["Calmar Ratio"]),
        "average_drawdown_percentage": safe_float(stats["Avg. Drawdown [%]"]),
        "max_drawdown_duration": str(stats["Max. Drawdown Duration"]),
        "average_drawdown_duration": str(stats["Avg. Drawdown Duration"]),
        "trade_count": stats["# Trades"],
        "win_rate": safe_float(stats["Win Rate [%]"]),
        "best_trade": safe_float(stats["Best Trade [%]"]),
        "worst_trade": safe_float(stats["Worst Trade [%]"]),
        "avg_trade": safe_float(stats["Avg. Trade [%]"]),
        "max_trade_duration": str(stats["Max. Trade Duration"]),
        "average_trade_duration": str(stats["Avg. Trade Duration"]),
        "profit_factor": safe_float(stats["Profit Factor"]),
        "html": html_content,
        "tpslRatio": 0.0,  # Not applicable for replay
        "sl_coef": 0.0,  # Not applicable for replay
    }

    return {
        "status": HTTP_200_OK,
        "message": "Backtest replay results",
        "data": backtest_stats_data,
    }


async def strategy_notification_job():
    """
    Fetch all unique strategies and run backtests + send notifications.
    Now fully async — safe to call from an async FastAPI endpoint.
    """
    strategies = await _get_all_strategies()

    print("--------------------------------------")
    print("Preparing to run backtests. Signal for:", strategies)
    print("--------------------------------------")
    logging.info(strategies)

    for strategy in strategies:
        logging.info(
            "Updating strategy backtest. Ticker: %s, Strategy: %s, Period: %s, Interval: %s",
            strategy.ticker,
            strategy.strategy,
            strategy.period,
            strategy.interval,
        )

        # last_optimized_at is returned as a native datetime by psycopg3
        last_optimized_at = strategy.last_optimized_at
        if last_optimized_at is None:
            time_difference = 999  # treat as never optimized → always optimize
        else:
            # Ensure tz-aware for comparison
            if last_optimized_at.tzinfo is None:
                last_optimized_at = last_optimized_at.replace(tzinfo=UTC)
            time_difference = (datetime.now(UTC) - last_optimized_at).days
        print("Skip optimization:", time_difference < 3)

        try:
            await get_backtest_result(
                ticker=strategy.ticker,
                interval=strategy.interval,
                period=strategy.period,
                strategy=strategy.strategy,
                parameters='{"max_longs": 2, "max_shorts": 2}',
                start=None,
                end=None,
                strategy_id=str(strategy.id) if strategy.id else None,
                notifications_on=strategy.notifications_on,
                skip_optimization=time_difference < 3,
                best_params={
                    "tpslRatio": strategy.tpsl_ratio,
                    "slcoef": strategy.sl_coef,
                    "TPcoef": strategy.tp_coef,
                },
            )
        except Exception as e:
            logging.error("Failed to run backtest for strategy: %s", e)


async def _get_all_strategies():
    """Fetch all unique strategies from Postgres via ORM."""
    async with AsyncSessionLocal() as session:
        return await UniqueStrategyRepository(session).get_all()


async def get_strategies():
    """
    Get the list of available trading strategies.

    Returns a list of strategies with their IDs, names, and optional descriptions.
    The strategy names are derived from the strategy_list configuration.
    """
    from app.signals.strategies.strategy_list import strategy_list
    from app.signals.dto import StrategyInfo

    strategies = []
    for strategy_id in strategy_list:
        # Convert strategy_id to a display name (capitalize and replace underscores)
        name = strategy_id.replace("_", " ").title()

        # Create strategy info object
        strategies.append(
            StrategyInfo(
                id=strategy_id,
                name=name,
                description=None,  # Can be extended later with descriptions
            )
        )

    return {
        "status": HTTP_200_OK,
        "message": "Available strategies",
        "data": strategies,
    }
