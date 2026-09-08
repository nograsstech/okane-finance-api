from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.basic_auth import get_current_username
from app.signals import router as signals_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(signals_router.router)
    app.dependency_overrides[get_current_username] = lambda: "test-user"
    return TestClient(app)


def test_background_backtest_returns_and_schedules_the_same_reference(monkeypatch):
    scheduled: dict[str, object] = {}

    async def fake_backtest(**kwargs):
        scheduled.update(kwargs)

    fixed_reference = "18de8932-e25a-40ea-91bb-4f90e1028fd5"
    monkeypatch.setattr(signals_router.service, "get_backtest_result", fake_backtest)
    monkeypatch.setattr(signals_router.uuid, "uuid4", lambda: fixed_reference)

    response = _client().get(
        "/signals/backtest",
        params={"ticker": "BTC-USD", "interval": "1h", "period": "5d"},
    )

    assert response.status_code == 200
    assert response.json() == fixed_reference
    assert scheduled["backtest_process_uuid"] == fixed_reference
