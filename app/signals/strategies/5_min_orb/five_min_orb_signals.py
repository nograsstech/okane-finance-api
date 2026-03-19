"""
5-Minute Opening Range Breakout (ORB) Signal Generator - Version A.

Version A: Immediate breakout entry
- Identifies opening range (first 5-min candle after session open)
- Detects breakouts: candle close above OR_High (long) or below OR_Low (short)
- Applies entry filters:
  - Don't chase if price moved >50% of OR size from breakout level
  - Skip if breakout candle wick > body (weak close)
  - Skip if past cutoff time (11:00 London / 12:00 NY)
- Generates signal on NEXT candle open after breakout close
- One trade per session (no re-entry)
"""

import importlib
from datetime import datetime, time, UTC
from typing import Any, Dict, Optional

import pandas as pd

# Import from module with numeric name using importlib
orb_utils = importlib.import_module("app.signals.strategies.5_min_orb.orb_utils")

convert_utc_to_session_time = orb_utils.convert_utc_to_session_time
calculate_pip_value = orb_utils.calculate_pip_value
calculate_or_size_pips = orb_utils.calculate_or_size_pips
get_or_threshold = orb_utils.get_or_threshold
should_skip_session = orb_utils.should_skip_session
detect_session_window = orb_utils.detect_session_window
MIN_OR_SIZE_PIPS = orb_utils.MIN_OR_SIZE_PIPS


def five_min_orb_signals(df: pd.DataFrame, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Generate ORB signals for Version A (immediate breakout entry).

    Args:
        df: DataFrame with OHLC data. Can have MultiIndex columns (yfinance format)
            or simple columns. Must have datetime index.
        parameters: Optional dict with:
            - ticker: Instrument ticker (default: 'EUR/USD')
            - session: 'london' or 'ny' (default: 'london')
            - chase_threshold: Max move as % of OR size (default: 0.5)
            - spread_buffer_pips: Buffer for spread (default: 2)

    Returns:
        DataFrame with added columns:
        - OR_High: OR high price
        - OR_Low: OR low price
        - OR_Size_Pips: OR size in pips
        - OR_Session: Session label ('london', 'ny', or None)
        - Pip_Value: Pip value for instrument
        - TotalSignal: 0=None, 1=Sell, 2=Buy
    """
    # Set default parameters
    if parameters is None:
        parameters = {}

    ticker = parameters.get("ticker", "EUR/USD")
    session = parameters.get("session", "london")
    chase_threshold = parameters.get("chase_threshold", 0.5)
    spread_buffer_pips = parameters.get("spread_buffer_pips", 2)

    # Make a copy to avoid modifying original
    df = df.copy()

    # Handle MultiIndex columns (yfinance format)
    if isinstance(df.columns, pd.MultiIndex):
        # Extract OHLC columns
        # Try common patterns
        if 'Close' in df.columns.get_level_values(0):
            # Flatten to simple columns
            df = df[['Open', 'High', 'Low', 'Close']].copy()
            df.columns = df.columns.droplevel(1)
        else:
            # Assume second level is the ticker
            df = df[[('Open', ticker), ('High', ticker), ('Low', ticker), ('Close', ticker)]].copy()
            df.columns = ['Open', 'High', 'Low', 'Close']

    # Ensure datetime index with timezone
    if df.index.tz is None:
        df.index = df.index.tz_localize(UTC)
    elif df.index.tz != UTC:
        df.index = df.index.tz_convert(UTC)

    # Drop rows with NaN values in OHLC
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])

    # Initialize new columns
    df['OR_High'] = None
    df['OR_Low'] = None
    df['OR_Size_Pips'] = None
    df['OR_Session'] = None
    df['Pip_Value'] = calculate_pip_value(ticker)
    df['TotalSignal'] = 0

    # State tracking
    or_state = {}  # Track OR state per date: {date_str: {or_high, or_low, or_size_pips, trade_taken}}
    pending_signal = None  # Track pending signal for next candle: {signal_type, timestamp}

    # Cutoff times in local time
    cutoff_times = {
        'london': time(11, 0),
        'ny': time(12, 0),
    }

    # Process each candle
    for idx, row in df.iterrows():
        # Convert to session local time
        local_time = convert_utc_to_session_time(idx, session)
        date_str = idx.strftime('%Y-%m-%d')

        # Initialize state for new date
        if date_str not in or_state:
            or_state[date_str] = {
                'or_high': None,
                'or_low': None,
                'or_size_pips': None,
                'or_time': None,
                'trade_taken': False,
                'skip_reason': None,
            }

        # Check if we have a pending signal from previous candle
        if pending_signal is not None:
            # Apply signal at this candle's open
            df.loc[idx, 'TotalSignal'] = pending_signal['signal_type']
            or_state[date_str]['trade_taken'] = True
            pending_signal = None
            continue

        # Skip if trade already taken this session
        if or_state[date_str]['trade_taken']:
            continue

        # Check cutoff time
        if local_time.time() >= cutoff_times[session]:
            continue

        # Detect session window
        window = detect_session_window(idx, session)

        if window == 'open':
            # This is the open candle (08:00 London or 09:30 NY)
            # OR will be the NEXT candle (08:05 or 09:35)
            pass

        elif window == 'active':
            # Within active window (after 08:05 London or 09:35 NY)

            # Check if OR has been identified yet
            if or_state[date_str]['or_high'] is None:
                # OR not yet identified - this candle IS the OR candle
                # (the first candle that closes after session open)

                # The current candle's OHLC data is the OR
                or_high = row['High']
                or_low = row['Low']
                pip_value = calculate_pip_value(ticker)
                or_size_pips = calculate_or_size_pips(or_high, or_low, pip_value)

                # Check if session should be skipped
                should_skip, skip_reason = should_skip_session(or_size_pips, ticker, session)

                if should_skip:
                    or_state[date_str]['skip_reason'] = skip_reason
                    or_state[date_str]['or_high'] = or_high
                    or_state[date_str]['or_low'] = or_low
                    or_state[date_str]['or_size_pips'] = or_size_pips
                    or_state[date_str]['or_time'] = idx
                else:
                    # Valid OR identified
                    or_state[date_str]['or_high'] = or_high
                    or_state[date_str]['or_low'] = or_low
                    or_state[date_str]['or_size_pips'] = or_size_pips
                    or_state[date_str]['or_time'] = idx

                # Set OR values for this candle
                df.loc[idx, 'OR_High'] = or_high
                df.loc[idx, 'OR_Low'] = or_low
                df.loc[idx, 'OR_Size_Pips'] = or_size_pips
                df.loc[idx, 'OR_Session'] = session

            else:
                # OR has been identified, check for breakouts

                # Skip if session was marked to skip
                if or_state[date_str]['skip_reason'] is not None:
                    continue

                or_high = or_state[date_str]['or_high']
                or_low = or_state[date_str]['or_low']
                or_size_pips = or_state[date_str]['or_size_pips']

                # Set OR values for all candles after OR formation
                df.loc[idx, 'OR_High'] = or_high
                df.loc[idx, 'OR_Low'] = or_low
                df.loc[idx, 'OR_Size_Pips'] = or_size_pips
                df.loc[idx, 'OR_Session'] = session

                # Check for long breakout (close above OR_High)
                if row['Close'] > or_high:
                    # Check entry filters

                    # 1. Chase threshold: don't chase if price moved too far
                    pip_value = calculate_pip_value(ticker)
                    move_from_or_high = (row['Close'] - or_high) / pip_value  # in pips
                    threshold_pips = or_size_pips * chase_threshold

                    if move_from_or_high > threshold_pips:
                        # Too far, skip
                        continue

                    # 2. Weak close: wick > body
                    body = abs(row['Close'] - row['Open'])
                    upper_wick = row['High'] - row['Close']
                    lower_wick = row['Open'] - row['Low']

                    # For long breakout, check upper wick
                    if upper_wick > body:
                        # Weak close, skip
                        continue

                    # All filters passed, schedule long signal for next candle
                    pending_signal = {'signal_type': 2, 'timestamp': idx}

                # Check for short breakout (close below OR_Low)
                elif row['Close'] < or_low:
                    # Check entry filters

                    # 1. Chase threshold
                    pip_value = calculate_pip_value(ticker)
                    move_from_or_low = (or_low - row['Close']) / pip_value  # in pips
                    threshold_pips = or_size_pips * chase_threshold

                    if move_from_or_low > threshold_pips:
                        # Too far, skip
                        continue

                    # 2. Weak close: wick > body
                    body = abs(row['Close'] - row['Open'])
                    upper_wick = row['High'] - row['Close']
                    lower_wick = row['Open'] - row['Low']

                    # For short breakout, check lower wick
                    if lower_wick > body:
                        # Weak close, skip
                        continue

                    # All filters passed, schedule short signal for next candle
                    pending_signal = {'signal_type': 1, 'timestamp': idx}

    return df
