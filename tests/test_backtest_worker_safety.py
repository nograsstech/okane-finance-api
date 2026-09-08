from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def test_strategy_import_uses_spawn_instead_of_fork() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import multiprocessing as mp; "
                "import app.signals.strategies.perform_backtest; "
                "print(mp.get_start_method(allow_none=True))"
            ),
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "spawn"


def test_backtest_requests_skip_optimization_by_default() -> None:
    assert _request().skip_optimization is True
    assert _request(skip_optimization=False).skip_optimization is False


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
async def test_healthcheck_probes_the_backtest_executor(monkeypatch) -> None:
    from app import health

    probed = False

    async def fake_to_thread(function, /, *args, **kwargs):
        nonlocal probed
        probed = True
        return function(*args, **kwargs)

    monkeypatch.setattr(health.asyncio, "to_thread", fake_to_thread)

    assert await health.healthcheck() == {"status": "ok"}
    assert probed is True


@pytest.mark.asyncio
async def test_healthcheck_fails_when_the_backtest_executor_is_unavailable(
    monkeypatch,
) -> None:
    from app import health

    async def timeout(_awaitable, *, timeout):
        _awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(health.asyncio, "wait_for", timeout)

    with pytest.raises(HTTPException) as error:
        await health.healthcheck()

    assert error.value.status_code == 503
