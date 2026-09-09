from __future__ import annotations

import asyncio
import functools
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from starlette.status import HTTP_200_OK

from app.db.postgres import AsyncSessionLocal
from app.db.repository import BacktestStatRepository, TradeActionRepository
from app.executors import BACKTEST_EXECUTOR
from app.notification.service import send_trade_action_notification
from app.signals.dto import BacktestResponseDTO, BacktestStats
from app.signals.services.results import (
    build_backtest_stats,
    build_persistence_payload,
    render_backtest_html,
)
from app.signals.strategies.calculate import calculate_signals
from app.signals.strategies.perform_backtest import perform_backtest
from app.signals.utils.yfinance import get_yfinance_data

logger = logging.getLogger(__name__)

BACKTEST_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class PersistenceResult:
    notifications_on: bool
    trade_actions: list[Any]


def _parse_parameters(parameters: str | None) -> dict[str, Any]:
    if parameters is None:
        return {}
    try:
        parsed = json.loads(parameters)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse parameters. Error: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400, detail="Failed to parse parameters. Expected an object"
        )
    return parsed


def _run_backtest(
    *,
    ticker: str,
    interval: str,
    period: str | None,
    strategy: str,
    parameters: dict[str, Any],
    start: str | None,
    end: str | None,
    skip_optimization: bool,
    best_params: dict[str, Any] | None,
) -> tuple[Any, Any, list[dict[str, Any]], dict[str, Any]]:
    frame = get_yfinance_data(ticker, interval, period, start, end)
    daily_frame = (
        get_yfinance_data(ticker, "1d", period, start, end) if strategy == "macd_1" else None
    )
    signals_frame = calculate_signals(frame, daily_frame, strategy, parameters)
    size = 0.01 if ticker == "BTC-USD" else 0.03
    return perform_backtest(
        signals_frame,
        strategy,
        {
            "best": False,
            "size": size,
            "slcoef": 2.2,
            "tpslRatio": 2.0,
            "max_longs": parameters.get("max_longs", 1),
            "max_shorts": parameters.get("max_shorts", 1),
        },
        skip_optimization,
        best_params,
    )


def _trade_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    for date_format in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return None


async def _persist_backtest_result(
    *,
    payload: dict[str, Any],
    trade_actions: list[dict[str, Any]],
    notifications_on: bool,
) -> PersistenceResult:
    """Persist one completed backtest using the existing upsert and deduplication rules."""
    async with AsyncSessionLocal() as session:
        backtest_repo = BacktestStatRepository(session)
        trade_repo = TradeActionRepository(session)

        updated_stat = None
        try:
            updated_stat = await backtest_repo.upsert(payload)
        except Exception:
            logger.exception(
                "Failed to save backtest stats for %s/%s",
                payload.get("ticker"),
                payload.get("strategy"),
            )

        computed_notifications_on = (
            payload["sharpe_ratio"] > 0 and payload["return_percentage"] > 0
        ) or payload["win_rate"] > 60
        existing_notifications_on = (
            updated_stat.notifications_on
            if updated_stat is not None and updated_stat.notifications_on is not None
            else None
        )
        if existing_notifications_on is None:
            payload["notifications_on"] = computed_notifications_on
            try:
                updated_stat = await backtest_repo.upsert(payload)
            except Exception:
                logger.exception("Failed to initialize notifications_on")
        else:
            payload["notifications_on"] = existing_notifications_on

        saved_actions: list[Any] = []
        actions_to_save = trade_actions
        if updated_stat is None:
            actions_to_save = actions_to_save[-1:]
        else:
            try:
                await backtest_repo.lock_for_trade_actions(updated_stat.id)
                latest_action = await trade_repo.get_latest_for_strategy(updated_stat.id)
                if latest_action is None:
                    actions_to_save = actions_to_save[-1:]
                else:
                    cutoff = latest_action.datetime
                    if cutoff is not None and cutoff.tzinfo is not None:
                        cutoff = cutoff.replace(tzinfo=None)
                    actions_to_save = [
                        action
                        for action in actions_to_save
                        if cutoff is not None
                        and (action_time := _trade_datetime(action.get("datetime"))) is not None
                        and action_time > cutoff
                    ]
                for action in actions_to_save:
                    action["backtest_id"] = updated_stat.id
            except Exception:
                logger.exception("Failed to deduplicate trade actions")
                actions_to_save = []

        if actions_to_save:
            try:
                saved_actions = await trade_repo.insert_many(actions_to_save)
            except Exception:
                logger.exception("Failed to save trade actions")

    return PersistenceResult(
        notifications_on=notifications_on,
        trade_actions=saved_actions,
    )


async def get_backtest_result(
    ticker: str,
    interval: str,
    period: str | None,
    strategy: str,
    parameters: str | None,
    start: str | None = None,
    end: str | None = None,
    strategy_id: str | None = None,
    backtest_process_uuid: str | None = None,
    notifications_on: bool = False,
    skip_optimization: bool = False,
    best_params: dict[str, Any] | None = None,
) -> BacktestResponseDTO:
    """Run, persist, and optionally notify for one strategy backtest."""
    parsed_parameters = _parse_parameters(parameters)
    try:
        loop = asyncio.get_running_loop()
        backtest, stats, trade_actions, strategy_parameters = await asyncio.wait_for(
            loop.run_in_executor(
                BACKTEST_EXECUTOR,
                functools.partial(
                    _run_backtest,
                    ticker=ticker,
                    interval=interval,
                    period=period,
                    strategy=strategy,
                    parameters=parsed_parameters,
                    start=start,
                    end=end,
                    skip_optimization=skip_optimization,
                    best_params=best_params,
                ),
            ),
            timeout=BACKTEST_TIMEOUT_SECONDS,
        )
        if backtest is None or stats is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Backtest returned no results (strategy calculation may have failed "
                    "or no trades were executed)."
                ),
            )
    except TimeoutError as exc:
        logger.error(
            "Backtest timed out after %ss for %s/%s",
            BACKTEST_TIMEOUT_SECONDS,
            ticker,
            strategy,
        )
        raise HTTPException(
            status_code=408,
            detail="Backtest timed out after 10 minutes. "
            "The strategy optimisation may be stalled; try again or skip optimization.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to run backtest. Error: {exc}"
        ) from exc

    html_content = await asyncio.to_thread(render_backtest_html, backtest, stats)
    reference = str(backtest_process_uuid) if backtest_process_uuid is not None else None
    public_stats: BacktestStats = build_backtest_stats(
        ticker=ticker,
        stats=stats,
        html_content=html_content,
        tpsl_ratio=strategy_parameters.get("tpslRatio"),
        sl_coef=strategy_parameters.get("slcoef"),
    )
    payload = build_persistence_payload(
        public_stats=public_stats,
        strategy=strategy,
        period=period,
        interval=interval,
        reference=reference,
        tpsl_ratio=strategy_parameters.get("tpslRatio"),
        sl_coef=strategy_parameters.get("slcoef"),
        tp_coef=strategy_parameters.get("TPcoef"),
    )
    for action in trade_actions:
        action["backtest_id"] = strategy_id

    persisted = await _persist_backtest_result(
        payload=payload,
        trade_actions=trade_actions,
        notifications_on=notifications_on,
    )
    if persisted.notifications_on and persisted.trade_actions:
        try:
            await asyncio.to_thread(
                send_trade_action_notification,
                strategy=strategy,
                ticker=ticker,
                interval=interval,
                trade_actions=persisted.trade_actions,
            )
        except Exception:
            logger.exception("Failed to send trade action notification")

    return BacktestResponseDTO(
        status=HTTP_200_OK,
        message="Backtest results",
        data=public_stats,
    )
