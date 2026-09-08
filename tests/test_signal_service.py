import pandas as pd
import pytest
from fastapi import HTTPException

from app.signals.services import signals


def _signal_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Volume": [1_000.0],
            "TotalSignal": [2.0],
        },
        index=pd.DatetimeIndex(["2024-01-01T00:00:00Z"]),
    )


@pytest.mark.asyncio
async def test_signal_service_returns_the_stable_response_envelope(monkeypatch):
    async def fake_market_data(*_args, **_kwargs):
        return _signal_frame()

    monkeypatch.setattr(signals, "get_yfinance_data_async", fake_market_data)
    monkeypatch.setattr(signals, "calculate_signals", lambda *_args: _signal_frame())

    response = await signals.get_signals(
        ticker="AAPL",
        interval="1d",
        period="5d",
        strategy="ema_bollinger",
        parameters=None,
    )

    assert response.status == 200
    assert response.data.ticker == "AAPL"
    assert response.data.signals.latest_signal.TotalSignal == 2.0
    assert len(response.data.signals.all_signals) == 1


@pytest.mark.asyncio
async def test_signal_service_translates_market_data_failures(monkeypatch):
    async def failing_market_data(*_args, **_kwargs):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(signals, "get_yfinance_data_async", failing_market_data)

    with pytest.raises(HTTPException) as error:
        await signals.get_signals(
            ticker="AAPL",
            interval="1d",
            period="5d",
            strategy="ema_bollinger",
            parameters=None,
        )

    assert error.value.status_code == 400
    assert error.value.detail == ("Failed to calculate signals. Error: provider timeout")


@pytest.mark.asyncio
async def test_signal_service_rejects_parameters_that_are_not_a_json_object():
    with pytest.raises(HTTPException) as error:
        await signals.get_signals(
            ticker="AAPL",
            interval="1d",
            period="5d",
            strategy="ema_bollinger",
            parameters="[]",
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Failed to parse parameters. Expected an object"
