"""
Repository layer for all Postgres ORM operations.

Each repository receives an AsyncSession and exposes typed async methods.
They replace all direct supabase.table(...) calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BacktestStat, TradeAction, UniqueStrategy


@runtime_checkable
class BacktestStatLike(Protocol):
    """Structural interface satisfied by both BacktestStat and the slim upsert result."""

    id: int
    notifications_on: bool | None


# ---------------------------------------------------------------------------
# BacktestStatRepository
# ---------------------------------------------------------------------------


class BacktestStatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, data: dict[str, Any]) -> BacktestStatLike | None:
        """
        Update an existing backtest stat matching the strategy config, or insert if none exists.
        Postgres doesn't have a unique constraint on these 4 columns, so we manually query.

        Only fetches `id` and `notifications_on` from the DB — avoids pulling the large
        html column (40–80 KB) just to check for row existence.

        On the UPDATE path, returns a SimpleNamespace(id, notifications_on) built entirely
        from in-memory data — no additional SELECT is needed, so html is never fetched.
        On the INSERT path, returns the full BacktestStat ORM object as before.
        """
        # Slim select: only the two columns we actually need
        stmt = select(BacktestStat.id, BacktestStat.notifications_on).where(
            BacktestStat.ticker == data.get("ticker"),
            BacktestStat.strategy == data.get("strategy"),
            BacktestStat.period == data.get("period"),
            BacktestStat.interval == data.get("interval"),
        )
        result = await self._session.execute(stmt)
        existing = result.first()  # Row(id, notifications_on) or None

        if existing:
            # Update in place via SQL UPDATE — no need to load the full ORM object
            update_data = {k: v for k, v in data.items() if k != "id"}
            await self._session.execute(
                sa_update(BacktestStat).where(BacktestStat.id == existing.id).values(**update_data)
            )
            await self._session.commit()

            # Build the return value from what we already have in memory.
            # The caller (_persist_backtest_result) only reads .id and .notifications_on,
            # so we never need to issue a get_by_id() SELECT (which would load html).
            return SimpleNamespace(
                id=existing.id,
                notifications_on=update_data.get("notifications_on"),
            )
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

    async def get_latest_for_strategy(self, backtest_id: int) -> TradeAction | None:
        """Return the most recent TradeAction for a given backtest_id."""
        stmt = (
            select(TradeAction)
            .where(TradeAction.backtest_id == backtest_id)
            .order_by(TradeAction.datetime.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert_many(self, records: list[dict[str, Any]]) -> list[TradeAction]:
        """Bulk-insert trade action records and return the created models."""
        if not records:
            return []
        stmt = pg_insert(TradeAction).values(records).returning(TradeAction)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return list(result.scalars().all())

    async def get_all_for_backtest(self, backtest_id: int) -> list[TradeAction]:
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
