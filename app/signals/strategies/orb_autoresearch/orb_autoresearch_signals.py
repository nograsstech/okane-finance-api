"""
ORB Autoresearch Signal Generator.

Based on 108-experiment autoresearch playbook (autoresearch-orb-0.1.0).
Key differences from 5_min_orb:
- 30-min opening range (6 × 5m bars)
- 2-bar skip after range forms before entries are considered
- 9-bar entry window (45 min)
- Tuesday–Friday only (skip Monday)
- Narrow (<0.2% range) vs Wide (>=0.2%) classification
- Directional filter: London+narrow → longs only; NY+narrow → shorts only; wide → both
- SL: narrow = 2/3 into range; wide = boundary
- TP: single target at 1× range height from entry
- 0.1% breakout threshold (close must clear range by 0.1%)
"""

import importlib
import logging
from datetime import timezone
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

orb_utils = importlib.import_module("app.signals.strategies.5_min_orb.orb_utils")
calculate_pip_value = orb_utils.calculate_pip_value
calculate_or_size_pips = orb_utils.calculate_or_size_pips

SIGNAL_NONE = 0
SIGNAL_SELL = 1
SIGNAL_BUY = 2

_DEFAULT_SESSIONS = [
    ("london", 8, 0, 12, 30),
    ("ny", 13, 30, 20, 0),
]


def _which_session(utc_dt, sessions_def):
    for name, oh, om, ch, cm in sessions_def:
        s = utc_dt.replace(hour=oh, minute=om, second=0, microsecond=0)
        e = utc_dt.replace(hour=ch, minute=cm, second=0, microsecond=0)
        if s <= utc_dt < e:
            return name
    return None


def orb_autoresearch_signals(
    df: pd.DataFrame,
    parameters: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Generate ORB Autoresearch signals.

    Args:
        df: DataFrame with OHLC data and datetime index.
        parameters: Optional dict with:
            - ticker: Instrument ticker (default: 'EURUSD')
            - opening_range_bars: Number of 5m bars for OR formation (default: 6 = 30 min)
            - breakout_threshold: Close must exceed range boundary by this fraction (default: 0.001)
            - skip_bars_after_range: Bars to skip after OR before entries allowed (default: 2)
            - entry_window_bars: Number of bars in entry window after skip (default: 9)
            - min_range_pct: Minimum range as fraction of price to trade session (default: 0.0003)
            - narrow_threshold: Fraction boundary for narrow vs wide (default: 0.002 = 0.2%)
            - allowed_weekdays: List of weekday ints 0=Mon…4=Fri (default: [1,2,3,4])
            - sessions: List of (name, open_h, open_m, close_h, close_m) in UTC

    Returns:
        DataFrame with added columns:
            OR_High, OR_Low, OR_Size_Pips, OR_Session, OR_Range_Pct,
            OR_Classification, Session_Active, Pip_Value, TotalSignal
    """
    if parameters is None:
        parameters = {}

    ticker = parameters.get("ticker", "EURUSD")
    opening_range_bars = int(parameters.get("opening_range_bars", 6))
    breakout_threshold = float(parameters.get("breakout_threshold", 0.001))
    skip_bars_after_range = int(parameters.get("skip_bars_after_range", 2))
    entry_window_bars = int(parameters.get("entry_window_bars", 9))
    min_range_pct = float(parameters.get("min_range_pct", 0.0003))
    narrow_threshold = float(parameters.get("narrow_threshold", 0.002))
    allowed_weekdays = list(parameters.get("allowed_weekdays", [1, 2, 3, 4]))
    sessions_def = parameters.get("sessions", _DEFAULT_SESSIONS)

    logger.debug(
        "orb_autoresearch_signals: shape=%s ticker=%s or_bars=%d",
        df.shape, ticker, opening_range_bars,
    )

    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            df = df[["Open", "High", "Low", "Close"]].copy()
            df.columns = df.columns.droplevel(1)
        else:
            df = df[
                [("Open", ticker), ("High", ticker), ("Low", ticker), ("Close", ticker)]
            ].copy()
            df.columns = ["Open", "High", "Low", "Close"]

    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
    elif df.index.tz != timezone.utc:
        df.index = df.index.tz_convert(timezone.utc)

    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    pip_value = calculate_pip_value(ticker)

    df["OR_High"] = None
    df["OR_Low"] = None
    df["OR_Size_Pips"] = None
    df["OR_Session"] = None
    df["OR_Range_Pct"] = None
    df["OR_Classification"] = None
    df["Session_Active"] = False
    df["Pip_Value"] = pip_value
    df["TotalSignal"] = SIGNAL_NONE

    session_state: dict = {}

    for idx, row in df.iterrows():
        if idx.weekday() not in allowed_weekdays:
            continue

        sess = _which_session(idx, sessions_def)
        if sess is None:
            continue

        df.at[idx, "Session_Active"] = True

        date_str = idx.strftime("%Y-%m-%d")
        key = f"{date_str}_{sess}"

        if key not in session_state:
            session_state[key] = {
                "b": 0,
                "or_highs": [],
                "or_lows": [],
                "range_high": None,
                "range_low": None,
                "range_pct": None,
                "classification": None,
                "range_set": False,
                "trade_taken": False,
                "skipped": False,
                "allowed": {"buy", "sell"},
            }

        state = session_state[key]
        b = state["b"]

        # Observation window: collect OR data
        if b < opening_range_bars:
            state["or_highs"].append(float(row["High"]))
            state["or_lows"].append(float(row["Low"]))
            state["b"] += 1
            continue

        # Compute range on the first bar after observation window
        if not state["range_set"]:
            range_high = max(state["or_highs"])
            range_low = min(state["or_lows"])
            range_height = range_high - range_low
            range_mid = (range_high + range_low) / 2
            range_pct = (range_height / range_mid) if range_mid > 0 else 0.0

            state["range_high"] = range_high
            state["range_low"] = range_low
            state["range_pct"] = range_pct
            state["range_set"] = True

            if range_height <= 0 or range_pct < min_range_pct:
                state["skipped"] = True
                state["trade_taken"] = True
            else:
                classification = "narrow" if range_pct < narrow_threshold else "wide"
                state["classification"] = classification
                if classification == "narrow":
                    state["allowed"] = {"buy"} if sess == "london" else {"sell"}
                else:
                    state["allowed"] = {"buy", "sell"}

        # Fill OR reference columns for all post-formation bars
        if state["range_high"] is not None:
            df.at[idx, "OR_High"] = state["range_high"]
            df.at[idx, "OR_Low"] = state["range_low"]
            df.at[idx, "OR_Range_Pct"] = state["range_pct"]
            df.at[idx, "OR_Classification"] = state["classification"]
            df.at[idx, "OR_Session"] = sess
            if pip_value > 0:
                df.at[idx, "OR_Size_Pips"] = calculate_or_size_pips(
                    state["range_high"], state["range_low"], pip_value
                )

        state["b"] += 1

        if state["trade_taken"]:
            continue

        # bars_since_range: 0 on the first bar after OR formation
        bars_since_range = b - opening_range_bars

        # Skip window (bars_since_range < skip) and beyond entry window
        if bars_since_range < skip_bars_after_range:
            continue
        if bars_since_range >= skip_bars_after_range + entry_window_bars:
            continue

        close = float(row["Close"])
        range_high = state["range_high"]
        range_low = state["range_low"]
        long_trigger = range_high * (1.0 + breakout_threshold)
        short_trigger = range_low * (1.0 - breakout_threshold)

        if close > long_trigger and "buy" in state["allowed"]:
            df.at[idx, "TotalSignal"] = SIGNAL_BUY
            state["trade_taken"] = True
        elif close < short_trigger and "sell" in state["allowed"]:
            df.at[idx, "TotalSignal"] = SIGNAL_SELL
            state["trade_taken"] = True

    total_signals = int((df["TotalSignal"] != SIGNAL_NONE).sum())
    logger.debug("orb_autoresearch_signals: total non-zero signals=%d", total_signals)

    return df
