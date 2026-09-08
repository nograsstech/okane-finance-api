from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from starlette.status import HTTP_200_OK

from app.db.postgres import AsyncSessionLocal
from app.db.repository import UniqueStrategyRepository
from app.signals.dto import StrategyInfo, StrategyListResponseDTO
from app.signals.services.backtests import get_backtest_result
from app.signals.strategies.strategy_list import strategy_list

logger = logging.getLogger(__name__)


def _build_best_params(strategy: Any) -> dict[str, Any] | None:
    """Map stored columns to the parameter names expected by each strategy."""
    if strategy.strategy == "mean_reversion_trend_filter":
        return {
            "slcoef": strategy.sl_coef if strategy.sl_coef is not None else 4.0,
            "tpratio": strategy.tp_coef if strategy.tp_coef is not None else 3.5,
        }
    if strategy.strategy == "orb_autoresearch":
        return None
    return {
        "tpslRatio": strategy.tpsl_ratio,
        "slcoef": strategy.sl_coef,
        "TPcoef": strategy.tp_coef,
    }


async def _get_all_strategies() -> list[Any]:
    async with AsyncSessionLocal() as session:
        return await UniqueStrategyRepository(session).get_all()


async def strategy_notification_job() -> None:
    """Refresh every stored strategy without letting one failure stop the job."""
    for strategy in await _get_all_strategies():
        try:
            last_optimized_at = strategy.last_optimized_at
            if last_optimized_at is None:
                days_since_optimization = 999
            else:
                if last_optimized_at.tzinfo is None:
                    last_optimized_at = last_optimized_at.replace(tzinfo=UTC)
                days_since_optimization = (datetime.now(UTC) - last_optimized_at).days

            await get_backtest_result(
                ticker=strategy.ticker,
                interval=strategy.interval,
                period=strategy.period,
                strategy=strategy.strategy,
                parameters='{"max_longs": 2, "max_shorts": 2}',
                strategy_id=str(strategy.id) if strategy.id else None,
                notifications_on=bool(strategy.notifications_on),
                skip_optimization=days_since_optimization < 3,
                best_params=_build_best_params(strategy),
            )
        except Exception:
            logger.exception(
                "Failed to refresh strategy %s/%s",
                getattr(strategy, "ticker", "unknown"),
                getattr(strategy, "strategy", "unknown"),
            )


async def get_strategies() -> StrategyListResponseDTO:
    strategies = [
        StrategyInfo(
            id=strategy_id,
            name=strategy_id.replace("_", " ").title(),
            description=None,
        )
        for strategy_id in strategy_list
    ]
    return StrategyListResponseDTO(
        status=HTTP_200_OK,
        message="Available strategies",
        data=strategies,
    )
