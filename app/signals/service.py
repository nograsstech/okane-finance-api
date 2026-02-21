import asyncio
import base64
import json
import logging
import os
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi import HTTPException
from starlette.status import HTTP_200_OK

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


async def get_signals(
    ticker, interval, period, strategy, parameters, start=None, end=None
):
    """Retrieves signals for a given ticker using the specified parameters."""
    try:
        df = None
        df1d = None
        try:
            df = await getYFinanceDataAsync(ticker, interval, period, start, end)
            if strategy == "macd_1":
                df1d = getYFinanceData(ticker, "1d", period, start, end)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to calculate signals. Error: {e}"
            )

        signals_df = None
        try:
            signals_df = await calculate_signals_async(df, df1d, strategy, parameters)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to calculate signals. Error: {e}"
            )
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
        raise HTTPException(
            status_code=400, detail=f"Failed to parse parameters. Error: {e}"
        )

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
                status_code=400, detail="Backtest returned no results (strategy calculation may have failed or no trades were executed)."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=400, detail=f"Failed to run backtest. Error: {e}"
        )

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
    if notifications_on and saved_trade_actions:
        print("Sending trade action notification to LINE group...")
        try:
            send_trade_action_notification(
                strategy=strategy,
                ticker=ticker,
                interval=interval,
                trade_actions=saved_trade_actions,
            )
        except Exception as e:
            logging.error(f"Failed to send LINE notification. Error: {e}")

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

        # Compute the metrics-based flag and persist it to the DB record.
        # NOTE: this does NOT override the `notifications_on` parameter that was
        # passed into this function — that value (from strategy.notifications_on)
        # is the authoritative source for whether to actually send a notification.
        good_sharpe = backtest_stats_data["sharpe_ratio"] > 0
        good_return = backtest_stats_data["return_percentage"] > 0
        good_winrate = backtest_stats_data["win_rate"] > 60
        computed_notifications_on = (good_sharpe and good_return) or good_winrate
        backtest_stats_data["notifications_on"] = computed_notifications_on
        print(
            f"Notifications — strategy flag: {notifications_on}, "
            f"computed flag: {computed_notifications_on} "
            f"(sharpe>0={good_sharpe}, return>0={good_return}, winrate>60={good_winrate})"
        )

        # Upsert backtest_stats
        updated_stat = None
        try:
            logging.info("Saving backtest stats to DB. Ticker: %s", ticker)
            updated_stat = await backtest_repo.upsert(backtest_stats_data)
        except Exception as e:
            logging.error("Failed to save backtest stats: %s", e)

        # Determine which trade actions are "new" by querying against the correct backtest_stat ID
        if updated_stat is not None:
            # print(f"[dedup] Querying latest trade action for backtest_stat.id={updated_stat.id}")
            latest_ta = await trade_repo.get_latest_for_strategy(updated_stat.id)
            # print(f"[dedup] Total backtest trade actions before filter: {len(trade_actions)}")

            if latest_ta is not None:
                # Strip tzinfo from both sides so naive/aware mismatches never raise TypeError.
                # psycopg3 can return TIMESTAMP WITHOUT TIME ZONE as tz-aware in some configs.
                cutoff_dt = latest_ta.datetime
                if hasattr(cutoff_dt, "tzinfo") and cutoff_dt.tzinfo is not None:
                    cutoff_dt = cutoff_dt.replace(tzinfo=None)
                # print(f"[dedup] Cutoff datetime (latest DB trade action): {cutoff_dt!r}")

                new_trade_actions = []
                for ta in trade_actions:
                    raw_dt = ta.get("datetime", "")
                    try:
                        ta_dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S.%f")
                    except (ValueError, TypeError):
                        try:
                            ta_dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError):
                            # logging.warning(
                            #     "[dedup] Could not parse trade action datetime: %s — skipping", raw_dt
                            # )
                            continue
                    passed = ta_dt > cutoff_dt
                    # print(f"[dedup]   ta_dt={ta_dt!r} > cutoff={cutoff_dt!r} → {passed}")
                    if passed:
                        new_trade_actions.append(ta)

                # print(f"[dedup] Actions passing filter: {len(new_trade_actions)}")
                trade_actions = new_trade_actions
            else:
                # print("[dedup] No existing trade actions in DB for this strategy — using last backtest action only")
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
                print("Trade actions saved to DB.")
        except Exception as e:
            logging.error("Failed to save trade actions: %s", e)

    return {
        "notifications_on": notifications_on,
        "trade_actions": saved_trade_actions,
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
            strategy.ticker, strategy.strategy, strategy.period, strategy.interval,
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
