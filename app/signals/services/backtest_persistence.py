"""
Backtest result persistence operations.

Handles all database writes for backtest results, including backtest stats
and trade actions. Extracted from service.py for better separation of concerns.
"""

import base64
import logging
import zlib
from datetime import UTC, datetime

from app.db.postgres import AsyncSessionLocal
from app.db.repository import (
    BacktestStatRepository,
    TradeActionRepository,
)


async def persist_backtest_result(
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
    """
    Persist backtest results to database.

    Handles the upsert of backtest statistics and insertion of new trade actions.
    Also computes and stores the notifications_on flag based on backtest performance.

    Args:
        ticker: Trading symbol
        interval: Time interval for the data
        period: Time period for the backtest
        strategy: Strategy name
        strategy_id: Database ID for the strategy
        backtest_process_uuid: UUID for this backtest run
        stats: Backtest statistics dictionary from backtesting.py
        html_content: HTML content for the backtest plot
        strategy_parameters: Parameters used in the backtest
        trade_actions: List of trade action dictionaries
        notifications_on: Whether notifications are enabled for this strategy

    Returns:
        dict with 'notifications_on' and 'trade_actions' keys
    """
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
