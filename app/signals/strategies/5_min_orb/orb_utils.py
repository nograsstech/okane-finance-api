"""
ORB utilities module.

Shared utilities for 5-minute Opening Range Breakout strategies.
Provides timezone conversion, session detection, and OR calculation functions.
"""

from datetime import datetime, time, UTC
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd

# Session windows in local time
SESSION_WINDOWS = {
    "london": {
        "open_time": time(8, 0),  # 08:00 London time
        "active_start": time(8, 5),  # 08:05 London time
        "active_end": time(11, 0),  # 11:00 London time
    },
    "ny": {
        "open_time": time(9, 30),  # 09:30 NY time
        "active_start": time(9, 35),  # 09:35 NY time
        "active_end": time(12, 0),  # 12:00 NY time
    },
}

# Timezone mappings
TIMEZONES = {
    "london": ZoneInfo("Europe/London"),
    "ny": ZoneInfo("America/New_York"),
}

# OR size thresholds in pips (instrument -> session -> max_pips)
OR_THRESHOLDS = {
    "EURUSD": {
        "london": 40,
        "ny": 35,
    },
    "GBPUSD": {
        "london": 50,
        "ny": 45,
    },
    "USDJPY": {
        "ny": 40,
    },
    "EURGBP": {
        "london": 40,
    },
    "GBPJPY": {
        "london": 45,
    },
}

# Minimum OR size in pips (skip if tighter)
MIN_OR_SIZE_PIPS = 5


def convert_utc_to_session_time(utc_time: datetime, session: str) -> datetime:
    """
    Convert UTC time to session local time with DST handling.

    Args:
        utc_time: UTC datetime with timezone info
        session: 'london' or 'ny'

    Returns:
        datetime in local time (naive, no timezone info)

    Raises:
        ValueError: If session is not supported
    """
    if session not in TIMEZONES:
        raise ValueError(f"Unsupported session: {session}")

    tz = TIMEZONES[session]
    return utc_time.astimezone(tz).replace(tzinfo=None)


def detect_session_window(utc_time: datetime, session: str) -> str | None:
    """
    Detect if the given time is within the active trading window.

    Returns:
        'open' if at the open time (first candle)
        'active' if within active trading window
        None if outside active window

    Args:
        utc_time: UTC datetime with timezone info
        session: 'london' or 'ny'

    Raises:
        ValueError: If session is not supported
    """
    if session not in SESSION_WINDOWS:
        raise ValueError(f"Unsupported session: {session}")

    local_time = convert_utc_to_session_time(utc_time, session)
    current_time = local_time.time()

    windows = SESSION_WINDOWS[session]

    # Check if at open time (exact match for first candle)
    if current_time == windows["open_time"]:
        return "open"

    # Check if within active window
    if windows["active_start"] <= current_time < windows["active_end"]:
        return "active"

    # Outside active window
    return None


def calculate_pip_value(ticker: str) -> float:
    """
    Calculate pip value for a given ticker.

    Args:
        ticker: Ticker symbol (e.g., 'EUR/USD' or 'EURUSD')

    Returns:
        Pip value (0.0001 for most pairs, 0.01 for JPY pairs)
    """
    # Normalize ticker format (remove slashes)
    normalized = ticker.replace("/", "").upper()

    # JPY pairs have 0.01 pip value
    if "JPY" in normalized:
        return 0.01

    # All other pairs have 0.0001 pip value
    return 0.0001


def calculate_or_size_pips(or_high: float, or_low: float, pip_value: float) -> float:
    """
    Calculate Opening Range size in pips.

    Args:
        or_high: High price of the OR
        or_low: Low price of the OR
        pip_value: Pip value for the instrument

    Returns:
        OR size in pips
    """
    range_size = or_high - or_low
    return range_size / pip_value


def get_or_threshold(ticker: str, session: str) -> int | None:
    """
    Get maximum OR size threshold for a ticker and session.

    Args:
        ticker: Ticker symbol (e.g., 'EUR/USD' or 'EURUSD')
        session: 'london' or 'ny'

    Returns:
        Maximum OR size in pips, or None if not configured
    """
    # Normalize ticker format
    normalized = ticker.replace("/", "").upper()

    if normalized in OR_THRESHOLDS:
        return OR_THRESHOLDS[normalized].get(session)

    return None


def should_skip_session(or_size_pips: float, ticker: str, session: str) -> tuple[bool, str | None]:
    """
    Determine if a session should be skipped based on OR size.

    Args:
        or_size_pips: OR size in pips
        ticker: Ticker symbol
        session: 'london' or 'ny'

    Returns:
        Tuple of (should_skip, reason)
        - should_skip: True if session should be skipped
        - reason: None if not skipping, otherwise explanation string
    """
    # Check minimum OR size
    if or_size_pips < MIN_OR_SIZE_PIPS:
        return True, f"OR size ({or_size_pips:.1f} pips) below minimum ({MIN_OR_SIZE_PIPS} pips)"

    # Check threshold if configured
    threshold = get_or_threshold(ticker, session)
    if threshold is not None and or_size_pips > threshold:
        return (
            True,
            f"OR size ({or_size_pips:.1f} pips) exceeds threshold ({threshold} pips)",
        )

    # Within acceptable range
    return False, None


def identify_opening_range(
    df: pd.DataFrame,
    ticker: str,
    session: str,
    date_str: str
) -> Optional[dict]:
    """
    Identify the Opening Range (OR) candle for a given session and date.

    The OR is defined as the first 5-minute candle that closes after the session open time.
    For example, if London opens at 08:00, the OR is the 08:00-08:05 candle.

    Args:
        df: DataFrame with OHLC data, indexed by UTC timestamps
        ticker: Ticker symbol (e.g., 'EUR/USD' or 'EURUSD')
        session: 'london' or 'ny'
        date_str: Date string in 'YYYY-MM-DD' format

    Returns:
        Dictionary with OR information:
        {
            'or_high': float,           # High price of the OR
            'or_low': float,            # Low price of the OR
            'or_size_pips': float,      # OR size in pips
            'or_time_index': pd.Timestamp,  # Timestamp of the OR candle (UTC)
            'skip': bool,               # True if session should be skipped
            'skip_reason': str | None   # Reason for skipping, or None
        }
        Returns None if no valid OR found (no data for the date)
    """
    if session not in SESSION_WINDOWS:
        raise ValueError(f"Unsupported session: {session}")

    # Parse the date and filter DataFrame to that date
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected 'YYYY-MM-DD'")

    # Ensure DataFrame index is timezone-aware
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize(UTC)
    elif df.index.tz != UTC:
        df = df.copy()
        df.index = df.index.tz_convert(UTC)

    # Filter to the target date (in UTC)
    target_date_start = datetime.combine(target_date, time.min).replace(tzinfo=UTC)
    target_date_end = datetime.combine(target_date, time.max).replace(tzinfo=UTC)

    df_day = df[(df.index >= target_date_start) & (df.index <= target_date_end)]

    if df_day.empty:
        return None

    # Get session open time in UTC for this date
    # The session open time varies by DST, so we need to calculate it
    session_open_local = SESSION_WINDOWS[session]["open_time"]

    # Find the first candle that closes after session open time
    or_candle = None
    for idx, row in df_day.iterrows():
        # Convert this candle's time to session local time
        local_time = convert_utc_to_session_time(idx, session)

        # Check if this candle closes after session open
        # A 5-min candle at 08:00-08:05 closes at 08:05
        candle_close_time = local_time.time()

        if candle_close_time > session_open_local:
            or_candle = row
            or_time_index = idx
            break

    if or_candle is None:
        return None

    # Extract OR high and low
    or_high = or_candle["High"]
    or_low = or_candle["Low"]

    # Calculate OR size in pips
    pip_value = calculate_pip_value(ticker)
    or_size_pips = calculate_or_size_pips(or_high, or_low, pip_value)

    # Check if session should be skipped
    should_skip, skip_reason = should_skip_session(or_size_pips, ticker, session)

    return {
        "or_high": or_high,
        "or_low": or_low,
        "or_size_pips": or_size_pips,
        "or_time_index": or_time_index,
        "skip": should_skip,
        "skip_reason": skip_reason,
    }
