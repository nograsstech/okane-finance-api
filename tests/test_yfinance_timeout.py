import pandas as pd

from app.signals.utils import yfinance as yfinance_module
from app.signals.utils.yfinance import _YFINANCE_DOWNLOAD_TIMEOUT_SECONDS, getYFinanceData


def _fake_yf_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2024-01-01 10:00:00"), pd.Timestamp("2024-01-01 11:00:00")],
        name="Datetime",
    )
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 2000],
        },
        index=idx,
    )


def test_get_yfinance_data_passes_timeout_to_download(monkeypatch):
    captured: dict = {}

    def fake_download(**kwargs):
        captured.update(kwargs)
        return _fake_yf_frame()

    monkeypatch.setattr(yfinance_module.yf, "download", fake_download)

    df = getYFinanceData(ticker="BTC-USD", interval="60m", period="5d")

    assert "timeout" in captured
    assert captured["timeout"] == _YFINANCE_DOWNLOAD_TIMEOUT_SECONDS
    assert captured["timeout"] is not None
    assert not df.empty
