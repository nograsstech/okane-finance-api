from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException


def _stats() -> dict[str, object]:
    return {
        "Start": datetime(2024, 1, 1),
        "End": datetime(2024, 1, 5),
        "Duration": pd.Timedelta(days=4),
        "Exposure Time [%]": 20.0,
        "Equity Final [$]": 10_500.0,
        "Equity Peak [$]": 10_750.0,
        "Return [%]": 5.0,
        "Buy & Hold Return [%]": 2.0,
        "Return (Ann.) [%]": 15.0,
        "Volatility (Ann.) [%]": 8.0,
        "Sharpe Ratio": 1.5,
        "Sortino Ratio": 2.0,
        "Calmar Ratio": 1.25,
        "Max. Drawdown [%]": -4.0,
        "Avg. Drawdown [%]": -1.0,
        "Max. Drawdown Duration": pd.Timedelta(days=1),
        "Avg. Drawdown Duration": pd.Timedelta(hours=12),
        "# Trades": 3,
        "Win Rate [%]": 66.667,
        "Best Trade [%]": 4.0,
        "Worst Trade [%]": -1.0,
        "Avg. Trade [%]": 1.5,
        "Max. Trade Duration": pd.Timedelta(hours=8),
        "Avg. Trade Duration": pd.Timedelta(hours=4),
        "Profit Factor": 2.5,
    }


class _FakeBacktest:
    def plot(self, *, filename: str, **_kwargs) -> None:
        Path(filename).write_text("<html>backtest</html>", encoding="utf-8")


class _SessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args) -> None:
        return None


class _BacktestRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def upsert(self, _data: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(id=7, notifications_on=False)

    async def lock_for_trade_actions(self, _backtest_id: int) -> None:
        return None


class _TradeRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def get_latest_for_strategy(
        self, _backtest_id: int
    ) -> SimpleNamespace | None:
        return None

    async def insert_many(
        self, actions: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        return actions


def _market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Volume": [1_000.0],
        },
        index=pd.DatetimeIndex(["2024-01-01"]),
    )


def _patch_successful_run(
    monkeypatch,
    backtests,
    backtest_repository=None,
    trade_repository=None,
    trade_actions: list[dict[str, object]] | None = None,
) -> None:
    frame = _market_frame()
    monkeypatch.setattr(backtests, "get_yfinance_data", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(backtests, "calculate_signals", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(
        backtests,
        "perform_backtest",
        lambda *_args, **_kwargs: (
            _FakeBacktest(),
            _stats(),
            trade_actions or [],
            {"tpslRatio": 2.0, "slcoef": 2.2},
        ),
    )
    monkeypatch.setattr(backtests, "AsyncSessionLocal", _SessionContext)
    monkeypatch.setattr(
        backtests,
        "BacktestStatRepository",
        backtest_repository or _BacktestRepository,
    )
    monkeypatch.setattr(
        backtests,
        "TradeActionRepository",
        trade_repository or _TradeRepository,
    )


@pytest.mark.asyncio
async def test_synchronous_backtest_returns_the_declared_stats_envelope(monkeypatch, tmp_path):
    from app.signals import service
    from app.signals.services import backtests

    monkeypatch.chdir(tmp_path)
    _patch_successful_run(monkeypatch, backtests)

    response = await service.get_backtest_result(
        ticker="AAPL",
        interval="1d",
        period="5d",
        strategy="ema_bollinger",
        parameters="{}",
    )
    payload = response.model_dump()

    assert payload["status"] == 200
    assert payload["message"] == "Backtest results"
    assert payload["data"]["ticker"] == "AAPL"
    assert payload["data"]["final_equity"] == 10_500.0
    assert payload["data"]["trade_count"] == 3
    assert payload["data"]["tpslRatio"] == 2.0
    assert payload["data"]["sl_coef"] == 2.2
    assert isinstance(payload["data"]["html"], str)


@pytest.mark.asyncio
async def test_backtest_still_returns_stats_when_persistence_fails(monkeypatch):
    from app.signals.services import backtests

    class FailingBacktestRepository(_BacktestRepository):
        async def upsert(self, _data: dict[str, object]) -> SimpleNamespace:
            raise RuntimeError("database unavailable")

    _patch_successful_run(monkeypatch, backtests, FailingBacktestRepository)

    response = await backtests.get_backtest_result(
        ticker="AAPL",
        interval="1d",
        period="5d",
        strategy="ema_bollinger",
        parameters="{}",
    )

    assert response.status == 200
    assert response.data.final_equity == 10_500.0


@pytest.mark.asyncio
async def test_backtest_persists_the_supplied_process_uuid(monkeypatch):
    from app.signals.services import backtests

    persisted_payloads: list[dict[str, object]] = []

    class CapturingBacktestRepository(_BacktestRepository):
        async def upsert(self, data: dict[str, object]) -> SimpleNamespace:
            persisted_payloads.append(data.copy())
            return await super().upsert(data)

    _patch_successful_run(monkeypatch, backtests, CapturingBacktestRepository)

    await backtests.get_backtest_result(
        ticker="AAPL",
        interval="1d",
        period="5d",
        strategy="ema_bollinger",
        parameters="{}",
        backtest_process_uuid="0d1826b6-a1ba-4a55-93fb-f03bb2396884",
    )

    assert persisted_payloads[0]["ref_id"] == "0d1826b6-a1ba-4a55-93fb-f03bb2396884"


@pytest.mark.asyncio
async def test_backtest_rejects_parameters_that_are_not_a_json_object():
    from app.signals import service

    with pytest.raises(HTTPException) as error:
        await service.get_backtest_result(
            ticker="AAPL",
            interval="1d",
            period="5d",
            strategy="ema_bollinger",
            parameters="[]",
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Failed to parse parameters. Expected an object"


@pytest.mark.asyncio
async def test_backtest_timeout_returns_request_timeout(monkeypatch):
    from app.signals.services import backtests

    async def timeout(awaitable, *, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        else:
            awaitable.cancel()
        raise TimeoutError

    monkeypatch.setattr(backtests.asyncio, "wait_for", timeout)

    with pytest.raises(HTTPException) as error:
        await backtests.get_backtest_result(
            ticker="AAPL",
            interval="1d",
            period="5d",
            strategy="ema_bollinger",
            parameters="{}",
        )

    assert error.value.status_code == 408
    assert "timed out after 10 minutes" in error.value.detail


@pytest.mark.asyncio
async def test_backtest_notifies_only_for_actions_newer_than_the_latest_saved_action(
    monkeypatch,
):
    from app.signals.services import backtests

    saved_actions: list[dict[str, object]] = []
    notifications: list[dict[str, object]] = []

    class DeduplicatingTradeRepository(_TradeRepository):
        async def get_latest_for_strategy(self, _backtest_id: int) -> SimpleNamespace:
            return SimpleNamespace(datetime=datetime(2024, 1, 2))

        async def insert_many(
            self, actions: list[dict[str, object]]
        ) -> list[dict[str, object]]:
            saved_actions.extend(actions)
            return actions

    actions: list[dict[str, object]] = [
        {"datetime": "2024-01-01 10:00:00", "trade_action": "buy"},
        {"datetime": "2024-01-03 10:00:00", "trade_action": "sell"},
    ]
    _patch_successful_run(
        monkeypatch,
        backtests,
        trade_repository=DeduplicatingTradeRepository,
        trade_actions=actions,
    )

    def capture_notification(**kwargs: object) -> None:
        notifications.append(kwargs)

    monkeypatch.setattr(backtests, "send_trade_action_notification", capture_notification)

    await backtests.get_backtest_result(
        ticker="AAPL",
        interval="1d",
        period="5d",
        strategy="ema_bollinger",
        parameters="{}",
        notifications_on=True,
    )

    assert [action["datetime"] for action in saved_actions] == ["2024-01-03 10:00:00"]
    assert len(notifications) == 1
    assert notifications[0]["trade_actions"] == saved_actions


@pytest.mark.asyncio
async def test_concurrent_persistence_deduplicates_trade_actions(monkeypatch):
    from app.signals.services import backtests

    lock = asyncio.Lock()
    latest_datetime: datetime | None = None
    saved_actions: list[dict[str, object]] = []

    class LockingSessionContext:
        def __init__(self) -> None:
            self.holds_lock = False

        async def __aenter__(self) -> LockingSessionContext:
            return self

        async def __aexit__(self, *_args: object) -> None:
            if self.holds_lock:
                lock.release()

    class LockingBacktestRepository(_BacktestRepository):
        def __init__(self, session: LockingSessionContext) -> None:
            self.session = session

        async def lock_for_trade_actions(self, _backtest_id: int) -> None:
            await lock.acquire()
            self.session.holds_lock = True

    class SharedTradeRepository(_TradeRepository):
        async def get_latest_for_strategy(
            self, _backtest_id: int
        ) -> SimpleNamespace | None:
            if latest_datetime is None:
                return None
            return SimpleNamespace(datetime=latest_datetime)

        async def insert_many(
            self, actions: list[dict[str, object]]
        ) -> list[dict[str, object]]:
            nonlocal latest_datetime
            saved_actions.extend(action.copy() for action in actions)
            latest_datetime = datetime.fromisoformat(str(actions[-1]["datetime"]))
            return actions

    monkeypatch.setattr(backtests, "AsyncSessionLocal", LockingSessionContext)
    monkeypatch.setattr(
        backtests, "BacktestStatRepository", LockingBacktestRepository
    )
    monkeypatch.setattr(backtests, "TradeActionRepository", SharedTradeRepository)

    payload = {
        "ticker": "AAPL",
        "strategy": "ema_bollinger",
        "sharpe_ratio": 1.0,
        "return_percentage": 2.0,
        "win_rate": 60.0,
    }
    action = {"datetime": "2024-01-03 10:00:00", "trade_action": "sell"}

    await asyncio.gather(
        backtests._persist_backtest_result(
            payload=payload.copy(),
            trade_actions=[action.copy()],
            notifications_on=True,
        ),
        backtests._persist_backtest_result(
            payload=payload.copy(),
            trade_actions=[action.copy()],
            notifications_on=True,
        ),
    )

    assert len(saved_actions) == 1
    assert saved_actions[0]["datetime"] == "2024-01-03 10:00:00"


@pytest.mark.asyncio
async def test_concurrent_html_renders_use_separate_temporary_files():
    from app.signals.services.results import render_backtest_html

    barrier = Barrier(2)
    rendered_paths: list[Path] = []

    class ConcurrentBacktest:
        def __init__(self, content: str) -> None:
            self.content = content

        def plot(self, *, filename: str, **_kwargs) -> None:
            output = Path(filename)
            rendered_paths.append(output)
            barrier.wait(timeout=2)
            output.write_text(self.content, encoding="utf-8")

    first, second = await asyncio.gather(
        asyncio.to_thread(render_backtest_html, ConcurrentBacktest("first"), {}),
        asyncio.to_thread(render_backtest_html, ConcurrentBacktest("second"), {}),
    )

    assert {first, second} == {"first", "second"}
    assert len(set(rendered_paths)) == 2
    assert all(not path.exists() for path in rendered_paths)
