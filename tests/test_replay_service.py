from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.signals.services import replay
from tests.test_backtest_service import _FakeBacktest, _stats


class _SessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args) -> None:
        return None


class _BacktestRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def get_replay_metadata(self, _backtest_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            ticker="AAPL",
            strategy="ema_bollinger",
            interval="1d",
            period="5d",
            start_time="2024-01-01",
            end_time="2024-01-05",
        )


class _TradeRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def get_all_for_backtest(self, _backtest_id: int) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                datetime=datetime(2024, 1, 2),
                trade_action="buy",
                entry_price=100.0,
                price=100.0,
                sl=95.0,
                tp=110.0,
                size=0.03,
            )
        ]


@pytest.mark.asyncio
async def test_replay_returns_fresh_stats_in_the_existing_envelope(monkeypatch):
    frame = pd.DataFrame(
        {"Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0]},
        index=pd.DatetimeIndex(["2024-01-02"]),
    )
    requested: dict[str, object] = {}

    def fake_market_data(**kwargs):
        requested.update(kwargs)
        return frame

    monkeypatch.setattr(replay, "AsyncSessionLocal", _SessionContext)
    monkeypatch.setattr(replay, "BacktestStatRepository", _BacktestRepository)
    monkeypatch.setattr(replay, "TradeActionRepository", _TradeRepository)
    monkeypatch.setattr(replay, "get_yfinance_data", fake_market_data)
    monkeypatch.setattr(
        replay,
        "run_replay",
        lambda *_args: (_FakeBacktest(), _stats(), [], {}),
    )

    response = await replay.replay_backtest(7)

    assert response.status == 200
    assert response.data.ticker == "AAPL"
    assert response.data.final_equity == 10_500.0
    assert requested["start"] == "2024-01-01"
    assert requested["end"] == "2024-01-05"
