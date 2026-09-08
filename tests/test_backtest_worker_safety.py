from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException

from app.signals.dto import SignalRequestDTO


def _request(**overrides: object) -> SignalRequestDTO:
    values: dict[str, object] = {
        "ticker": "AAPL",
        "period": "5d",
        "interval": "1d",
        "strategy": "ema_bollinger",
    }
    values.update(overrides)
    return SignalRequestDTO(**values)


def test_strategy_import_uses_threaded_optimizer_without_changing_process_context() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import multiprocessing as mp; "
                "from multiprocessing.dummy import Pool; "
                "import backtesting; "
                "import app.signals.strategies.perform_backtest; "
                "print(mp.get_start_method(allow_none=True)); "
                "print(backtesting.Pool is Pool)"
            ),
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().splitlines() == ["None", "True"]


def test_backtest_requests_skip_optimization_by_default() -> None:
    assert _request().skip_optimization is True
    assert _request(skip_optimization=False).skip_optimization is False


def test_dispatched_backtests_accept_optimization_control() -> None:
    from app.signals.strategies import perform_backtest as dispatcher

    backtests = [
        value
        for name, value in vars(dispatcher).items()
        if name.endswith("_backtest") and callable(value)
    ]

    assert backtests
    assert all(
        "skip_optimization" in inspect.signature(backtest).parameters
        for backtest in backtests
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "app.signals.strategies.clf_bollinger_rsi.clf_bollinger_rsi_backtest",
        "app.signals.strategies.clf_bollinger_rsi.clf_bollinger_rsi_backtest_15m",
        "app.signals.strategies.clf_bollinger_rsi.eurjpy_bollinger_rsi_60m_backtest",
    ],
)
def test_legacy_backtests_supply_defaults_when_optimization_is_skipped(
    monkeypatch,
    module_name: str,
) -> None:
    module = importlib.import_module(module_name)

    class FakeBacktest:
        def __init__(self, _frame, _strategy, **_kwargs) -> None:
            self._strategy = SimpleNamespace(trades_actions=[])

        def run(self) -> dict[str, object]:
            return {}

    monkeypatch.setattr(module, "Backtest", FakeBacktest)
    frame = pd.DataFrame({"TotalSignal": [0]})

    _, _, _, parameters = module.backtest(
        frame,
        {"best": False},
        skip_optimization=True,
    )

    assert parameters == {
        "best": True,
        "TPcoef": 2,
        "slcoef": 3,
        "tpslRatio": 2 / 3,
    }


@pytest.mark.asyncio
async def test_sync_backtest_forwards_optimization_choice(monkeypatch) -> None:
    from app.signals import router

    captured: dict[str, object] = {}

    async def fake_get_backtest_result(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": 200, "message": "Backtest results", "data": None}

    monkeypatch.setattr(router.service, "get_backtest_result", fake_get_backtest_result)

    await router.backtest_sync("user", _request(skip_optimization=False))

    assert captured["skip_optimization"] is False


@pytest.mark.asyncio
async def test_background_backtest_forwards_optimization_choice() -> None:
    from app.signals import router

    captured: dict[str, object] = {}

    class BackgroundTasks:
        def add_task(self, _function, **kwargs: object) -> None:
            captured.update(kwargs)

    await router.backtest(
        "user",
        BackgroundTasks(),
        _request(skip_optimization=False),
    )

    assert captured["skip_optimization"] is False


@pytest.mark.asyncio
async def test_healthcheck_probes_the_backtest_executor() -> None:
    from app import health
    from app.signals import service

    assert health.BACKTEST_EXECUTOR is service.BACKTEST_EXECUTOR
    assert await health.healthcheck() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthcheck_fails_when_the_backtest_executor_is_unavailable(
    monkeypatch,
) -> None:
    from app import health

    async def timeout(_awaitable, *, timeout):
        _awaitable.cancel()
        raise TimeoutError

    monkeypatch.setattr(health.asyncio, "wait_for", timeout)

    with pytest.raises(HTTPException) as error:
        await health.healthcheck()

    assert error.value.status_code == 503
