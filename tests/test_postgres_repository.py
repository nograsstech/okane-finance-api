"""
Unit tests for the Postgres repository layer.

Uses an in-memory SQLite database (via aiosqlite) — no live Postgres required.

Note: SQLite does not support server-side gen_random_uuid(), so test fixtures
supply UUIDs explicitly.
"""

from __future__ import annotations

import pytest

from app.db.repository import (
    BacktestStatRepository,
    TradeActionRepository,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backtest_payload(**overrides) -> dict:
    return {
        "ticker": "AAPL",
        "strategy": "macd_1",
        "period": "1y",
        "interval": "1d",
        "sharpe_ratio": 1.5,
        "return_percentage": 12.3,
        "win_rate": 55.0,
        "trade_count": 42,
        "notifications_on": True,
        # omit other optional fields — they are nullable
        **overrides,
    }


_trade_id_counter = 0

def _trade_action_payload(backtest_id: int, dt: str = "2024-01-01T00:00:00") -> dict:
    global _trade_id_counter
    _trade_id_counter += 1
    return {
        "id": _trade_id_counter,
        "backtest_id": backtest_id,
        "datetime": dt,
        "trade_action": "buy",
        "price": 150.0,
        "pnl": 5.0,
        "return_pct": 3.3,
    }


# ---------------------------------------------------------------------------
# BacktestStatRepository
# ---------------------------------------------------------------------------


class TestBacktestStatRepository:
    async def test_insert_creates_record(self, db_session):
        repo = BacktestStatRepository(db_session)
        data = _backtest_payload()
        stat = await repo.insert(data)
        assert stat is not None
        assert stat.ticker == "AAPL"

    async def test_insert_returns_correct_id(self, db_session):
        repo = BacktestStatRepository(db_session)
        stat = await repo.insert(_backtest_payload(id=101))
        assert stat.id == 101

    async def test_upsert_creates_when_missing(self, db_session):
        repo = BacktestStatRepository(db_session)
        data = _backtest_payload()
        stat = await repo.upsert(data)
        assert stat is not None
        assert stat.id is not None

    async def test_upsert_updates_when_existing(self, db_session):
        repo = BacktestStatRepository(db_session)
        stat = await repo.insert(_backtest_payload(ticker="NVDA", sharpe_ratio=1.0))

        updated = await repo.upsert(_backtest_payload(ticker="NVDA", sharpe_ratio=2.5))
        assert updated is not None
        assert updated.sharpe_ratio == 2.5
        assert updated.id == stat.id

    async def test_insert_multiple_records(self, db_session):
        repo = BacktestStatRepository(db_session)
        for i in range(3):
            stat = await repo.insert(_backtest_payload(ticker=f"TICK{i}"))
            assert stat is not None
            assert stat.ticker == f"TICK{i}"


# ---------------------------------------------------------------------------
# TradeActionRepository
# ---------------------------------------------------------------------------


class TestTradeActionRepository:
    async def test_insert_many_returns_all_records(self, db_session):
        repo = TradeActionRepository(db_session)
        # First we need a backtest stat in the DB (FK constraint)
        stat = await BacktestStatRepository(db_session).insert(_backtest_payload())
        stat_id = stat.id

        records = [
            _trade_action_payload(stat_id, f"2024-01-0{i + 1}T00:00:00")
            for i in range(3)
        ]
        saved = await repo.insert_many(records)
        assert len(saved) == 3

    async def test_insert_many_empty_list_returns_empty(self, db_session):
        repo = TradeActionRepository(db_session)
        result = await repo.insert_many([])
        assert result == []

    async def test_get_latest_for_strategy_returns_newest(self, db_session):
        stat = await BacktestStatRepository(db_session).insert(_backtest_payload())
        stat_id = stat.id

        ta_repo = TradeActionRepository(db_session)
        await ta_repo.insert_many([
            _trade_action_payload(stat_id, "2024-01-01T00:00:00"),
            _trade_action_payload(stat_id, "2024-03-01T00:00:00"),
            _trade_action_payload(stat_id, "2024-02-01T00:00:00"),
        ])

        latest = await ta_repo.get_latest_for_strategy(stat_id)
        assert latest is not None
        assert latest.datetime == "2024-03-01T00:00:00"

    async def test_get_latest_for_strategy_returns_none_when_empty(self, db_session):
        repo = TradeActionRepository(db_session)
        result = await repo.get_latest_for_strategy(999)
        assert result is None
