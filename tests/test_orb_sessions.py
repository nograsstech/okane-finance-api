import pandas as pd

from app.signals.strategies.five_min_orb.five_min_orb_signals import (
    five_min_orb_signals,
)


def test_five_min_orb_processes_london_and_new_york_sessions() -> None:
    index = pd.date_range(
        start="2025-03-18 07:00:00",
        end="2025-03-18 17:00:00",
        freq="5min",
        tz="UTC",
    )
    df = pd.DataFrame(
        {
            "Open": [1.0850] * len(index),
            "High": [1.0860] * len(index),
            "Low": [1.0840] * len(index),
            "Close": [1.0855] * len(index),
        },
        index=index,
    )

    df.loc["2025-03-18 08:05:00", ["Open", "High", "Low", "Close"]] = [
        1.0850,
        1.0860,
        1.0840,
        1.0855,
    ]
    df.loc["2025-03-18 08:10:00", ["Open", "High", "Low", "Close"]] = [
        1.0856,
        1.0872,
        1.0855,
        1.0870,
    ]
    df.loc["2025-03-18 13:35:00", ["Open", "High", "Low", "Close"]] = [
        1.0870,
        1.0890,
        1.0865,
        1.0875,
    ]
    df.loc["2025-03-18 13:40:00", ["Open", "High", "Low", "Close"]] = [
        1.0876,
        1.0900,
        1.0875,
        1.0898,
    ]

    result = five_min_orb_signals(
        df,
        parameters={"ticker": "EUR/USD", "session": "both"},
    )
    signal_sessions = result.loc[result["TotalSignal"] != 0, "OR_Session"].tolist()

    assert signal_sessions == ["london", "ny"]
