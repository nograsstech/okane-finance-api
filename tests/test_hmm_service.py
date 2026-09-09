import pandas as pd
import pytest

from app.signals import hmm_service
from app.signals.hmm_dto import DominantRegime


def _regime_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [100.0, 98.0],
            "obs_momentum": [0.8, -0.7],
            "obs_volatility": [0.2, 0.5],
            "obs_rsi": [0.6, -0.5],
            "prob_bull": [75.0, 15.0],
            "prob_bear": [10.0, 72.0],
            "prob_chop": [15.0, 13.0],
            "prob_bull_smoothed": [80.0, 12.0],
            "prob_bear_smoothed": [8.0, 76.0],
            "prob_chop_smoothed": [12.0, 12.0],
            "regime": ["bull", "bear"],
            "regime_state": [1, -1],
            "confidence": [75.0, 72.0],
            "confidence_entropy": [60.0, 58.0],
            "confidence_margin": [60.0, 57.0],
            "bars_in_regime": [1, 1],
        },
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]),
    )


@pytest.mark.asyncio
async def test_hmm_service_builds_summary_transitions_and_statistics(monkeypatch):
    async def fake_market_data(**_kwargs):
        return pd.DataFrame({"Close": [100.0, 98.0]})

    monkeypatch.setattr(hmm_service, "getYFinanceDataAsync", fake_market_data)
    monkeypatch.setattr(hmm_service, "calculate_hmm_regime", lambda **_kwargs: _regime_frame())

    response = await hmm_service.get_hmm_regime_data(
        ticker="AAPL",
        interval="1d",
        period="5d",
    )

    assert response.status == 200
    assert response.data_points == 2
    assert response.summary.current_regime == DominantRegime.BEAR
    assert response.summary.confidence == "HIGH"
    assert len(response.transition_events) == 1
    assert response.transition_events[0].from_regime == DominantRegime.BULL
    assert response.transition_events[0].to_regime == DominantRegime.BEAR
    stats = {item.regime: item for item in response.regime_statistics}
    assert stats[DominantRegime.BULL].total_bars == 1
    assert stats[DominantRegime.BEAR].total_bars == 1


@pytest.mark.asyncio
async def test_hmm_service_rejects_empty_market_data(monkeypatch):
    async def empty_market_data(**_kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(hmm_service, "getYFinanceDataAsync", empty_market_data)

    with pytest.raises(ValueError, match="No data available for ticker AAPL"):
        await hmm_service.get_hmm_regime_data(ticker="AAPL", period="5d")
