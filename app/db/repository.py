"""
Repository layer for all Postgres ORM operations.

Each repository receives an AsyncSession and exposes typed async methods.
They replace all direct supabase.table(...) calls.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BacktestStat, TradeAction, UniqueStrategy

# ---------------------------------------------------------------------------
# BacktestStatRepository
# ---------------------------------------------------------------------------


class BacktestStatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, data: dict[str, Any]) -> BacktestStat | None:
        """
        Update an existing backtest stat matching the strategy config, or insert if none exists.
        Postgres doesn't have a unique constraint on these 4 columns, so we manually query.
        """
        stmt = select(BacktestStat).where(
            BacktestStat.ticker == data.get("ticker"),
            BacktestStat.strategy == data.get("strategy"),
            BacktestStat.period == data.get("period"),
            BacktestStat.interval == data.get("interval"),
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            for k, v in data.items():
                if k != "id":
                    setattr(existing, k, v)
            await self._session.commit()
            return existing
        else:
            return await self.insert(data)

    async def insert(self, data: dict[str, Any]) -> BacktestStat | None:
        """INSERT a new row and return the created model."""
        stmt = pg_insert(BacktestStat).values(**data).returning(BacktestStat)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one_or_none()

    async def get_by_id(self, backtest_id: int) -> BacktestStat | None:
        """Return a BacktestStat by its ID."""
        stmt = select(BacktestStat).where(BacktestStat.id == backtest_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# TradeActionRepository
# ---------------------------------------------------------------------------


class TradeActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_for_strategy(
        self, backtest_id: int
    ) -> TradeAction | None:
        """Return the most recent TradeAction for a given backtest_id."""
        stmt = (
            select(TradeAction)
            .where(TradeAction.backtest_id == backtest_id)
            .order_by(TradeAction.datetime.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert_many(
        self, records: list[dict[str, Any]]
    ) -> list[TradeAction]:
        """Bulk-insert trade action records and return the created models."""
        if not records:
            return []
        stmt = pg_insert(TradeAction).values(records).returning(TradeAction)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return list(result.scalars().all())

    async def get_all_for_backtest(
        self, backtest_id: int
    ) -> list[TradeAction]:
        """Return all TradeActions for a given backtest_id, ordered by datetime."""
        stmt = (
            select(TradeAction)
            .where(TradeAction.backtest_id == backtest_id)
            .order_by(TradeAction.datetime.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# UniqueStrategyRepository
# ---------------------------------------------------------------------------


class UniqueStrategyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[UniqueStrategy]:
        """Return all unique strategies."""
        result = await self._session.execute(select(UniqueStrategy))
        return list(result.scalars().all())
