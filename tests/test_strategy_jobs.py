from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.signals.services import strategy_jobs
from app.signals.strategies.strategy_list import strategy_list


def _strategy(strategy_id: int, *, recent: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=strategy_id,
        ticker=f"TICK{strategy_id}",
        strategy="ema_bollinger",
        period="30d",
        interval="1d",
        notifications_on=True,
        last_optimized_at=(datetime.now(UTC) - timedelta(days=1)) if recent else None,
        tpsl_ratio=2.0,
        sl_coef=2.2,
        tp_coef=None,
    )


@pytest.mark.asyncio
async def test_strategy_list_uses_the_public_strategy_identifiers():
    response = await strategy_jobs.get_strategies()

    assert [item.id for item in response.data] == strategy_list
    assert "5_min_orb" in [item.id for item in response.data]
    assert "five_min_orb" not in [item.id for item in response.data]


@pytest.mark.asyncio
async def test_strategy_job_continues_after_one_backtest_fails(monkeypatch):
    requested: list[dict[str, object]] = []

    async def fake_strategies():
        return [_strategy(1, recent=True), _strategy(2, recent=False)]

    async def fake_backtest(**kwargs):
        requested.append(kwargs)
        if kwargs["ticker"] == "TICK1":
            raise RuntimeError("first strategy failed")

    monkeypatch.setattr(strategy_jobs, "_get_all_strategies", fake_strategies)
    monkeypatch.setattr(strategy_jobs, "get_backtest_result", fake_backtest)

    await strategy_jobs.strategy_notification_job()

    assert [request["ticker"] for request in requested] == ["TICK1", "TICK2"]
    assert requested[0]["skip_optimization"] is True
    assert requested[1]["skip_optimization"] is False


@pytest.mark.asyncio
async def test_strategy_job_isolates_failures_before_backtest_execution(monkeypatch):
    requested: list[str] = []
    invalid = _strategy(1, recent=True)
    invalid.last_optimized_at = "not-a-datetime"

    async def fake_strategies():
        return [invalid, _strategy(2, recent=False)]

    async def fake_backtest(**kwargs):
        requested.append(kwargs["ticker"])

    monkeypatch.setattr(strategy_jobs, "_get_all_strategies", fake_strategies)
    monkeypatch.setattr(strategy_jobs, "get_backtest_result", fake_backtest)

    await strategy_jobs.strategy_notification_job()

    assert requested == ["TICK2"]
