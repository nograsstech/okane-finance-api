from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import HTTPException
from starlette.status import HTTP_200_OK

from app.db.postgres import AsyncSessionLocal
from app.db.repository import BacktestStatRepository, TradeActionRepository
from app.signals.dto import BacktestReplayResponseDTO
from app.signals.services.results import build_backtest_stats, render_backtest_html
from app.signals.strategies.replay.predefined_trade_strategy import backtest as run_replay
from app.signals.utils.yfinance import get_yfinance_data

logger = logging.getLogger(__name__)

REPLAY_TIMEOUT_SECONDS = 120


def _as_trade_schedule(actions: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "datetime": (
                action.datetime.strftime("%Y-%m-%d %H:%M:%S.%f") if action.datetime else None
            ),
            "trade_action": action.trade_action,
            "entry_price": action.entry_price,
            "price": action.price,
            "sl": action.sl,
            "tp": action.tp,
            "size": action.size,
        }
        for action in actions
    ]


def _required_metadata(metadata: Any) -> tuple[str, str, str]:
    missing = [
        name for name in ("ticker", "interval", "period") if not getattr(metadata, name, None)
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Backtest is missing required fields: {', '.join(missing)}",
        )
    return str(metadata.ticker), str(metadata.interval), str(metadata.period)


async def replay_backtest(backtest_id: int) -> BacktestReplayResponseDTO:
    """Replay stored trade actions against a fresh yfinance data set."""
    async with AsyncSessionLocal() as session:
        backtest_repo = BacktestStatRepository(session)
        trade_repo = TradeActionRepository(session)
        metadata = await backtest_repo.get_replay_metadata(backtest_id)
        if metadata is None:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest with ID {backtest_id} not found",
            )
        actions = await trade_repo.get_all_for_backtest(backtest_id)
        if not actions:
            raise HTTPException(
                status_code=404,
                detail=f"No trade actions found for backtest ID {backtest_id}",
            )

    ticker, interval, period = _required_metadata(metadata)
    trade_schedule = _as_trade_schedule(actions)

    def replay() -> tuple[Any, Any, Any, Any]:
        frame = get_yfinance_data(
            ticker=ticker,
            interval=interval,
            period=period,
            start=metadata.start_time,
            end=metadata.end_time,
        )
        if frame.empty:
            raise ValueError(f"No data returned from yfinance for {ticker}")
        return run_replay(frame, trade_schedule)

    try:
        backtest, stats, _, _ = await asyncio.wait_for(
            asyncio.to_thread(replay),
            timeout=REPLAY_TIMEOUT_SECONDS,
        )
        if backtest is None or stats is None:
            raise HTTPException(status_code=400, detail="Backtest replay returned no results.")
    except TimeoutError as exc:
        logger.error("Replay timed out for backtest_id=%s", backtest_id)
        raise HTTPException(
            status_code=408,
            detail=f"Backtest replay timed out after {REPLAY_TIMEOUT_SECONDS}s. "
            "The data source may be stalled; try again.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to replay backtest. Error: {exc}",
        ) from exc

    try:
        html_content = await asyncio.wait_for(
            asyncio.to_thread(render_backtest_html, backtest, stats),
            timeout=REPLAY_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail=f"Backtest replay timed out after {REPLAY_TIMEOUT_SECONDS}s during HTML render.",
        ) from exc

    return BacktestReplayResponseDTO(
        status=HTTP_200_OK,
        message="Backtest replay results",
        data=build_backtest_stats(
            ticker=ticker,
            stats=stats,
            html_content=html_content,
            tpsl_ratio=0.0,
            sl_coef=0.0,
        ),
    )
