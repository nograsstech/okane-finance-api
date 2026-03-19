"""
5-Minute Opening Range Breakout (ORB) Signal Generator - Version B.

Version B: Breakout with retest confirmation (three-step process)
Step 1 - Initial Breakout (Observation Only):
- Detect candle close above OR_High (potential long) or below OR_Low (potential short)
- Set breakout_detected = True
- Set breakout_direction = 'long' or 'short'
- Record breakout_time
- DO NOT generate signal yet

Step 2 - Wait for Retest:
- After breakout, monitor for price returning to OR level
- Retest tolerance: 2-3 pips from OR level
- Timeout: 6 candles (30 minutes) after breakout
- If no retest within timeout → Skip session (reset state)

Step 3 - Confirmation (Entry Trigger):
After retest occurs, look for:

Option A - Candle Close:
- Candle touches OR level and closes back in breakout direction
- Long: Close > OR_High after touching it
- Short: Close < OR_Low after touching it
- Signal on NEXT candle after confirmation close

Option B - Rejection Wick:
- Rejection wick at OR level
- Wick ≥ 2× body size
- Long: Lower wick at OR_High (bullish rejection)
- Short: Upper wick at OR_Low (bearish rejection)
- Signal AT rejection candle close
"""

import importlib
from datetime import UTC, time
from typing import Any

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

# Signal value constants
SIGNAL_NONE = 0
SIGNAL_SELL = 1
SIGNAL_BUY = 2


def five_min_orb_confirmation_signals(
    df: pd.DataFrame, parameters: dict[str, Any] | None = None
) -> pd.DataFrame:
    """
    Generate ORB signals for Version B (breakout with retest confirmation).

    Three-step process:
    1. Detect breakout (observation only)
    2. Wait for retest within timeout
    3. Confirm with close or rejection wick

    Args:
        df: DataFrame with OHLC data. Can have MultiIndex columns (yfinance format)
            or simple columns. Must have datetime index.
        parameters: Optional dict with:
            - ticker: Instrument ticker (default: 'EUR/USD')
            - session: 'london' or 'ny' (default: 'london')
            - retest_tolerance_pips: Tolerance for retest in pips (default: 3)
            - entry_timeout_bars: Timeout in bars after breakout (default: 6)

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
    retest_tolerance_pips = parameters.get("retest_tolerance_pips", 3)
    entry_timeout_bars = parameters.get("entry_timeout_bars", 6)

    # Input validation
    if retest_tolerance_pips < 0:
        raise ValueError("retest_tolerance_pips must be non-negative")
    if entry_timeout_bars < 0:
        raise ValueError("entry_timeout_bars must be non-negative")

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

    # State tracking per date
    or_state = {}  # Track OR state per date

    # Calculate pip value once
    pip_value = calculate_pip_value(ticker)
    retest_tolerance = retest_tolerance_pips * pip_value

    # Track pending signal across candles
    pending_signal = None  # (signal_type, timestamp)

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
                'skip_reason': None,
                'trade_taken': False,
                # Version B state
                'breakout_detected': False,
                'breakout_direction': None,
                'breakout_time': None,
                'bars_since_breakout': 0,
                'retest_occurred': False,
            }

        # Check if we have a pending signal from previous candle
        if pending_signal is not None:
            # Apply signal at this candle's open
            df.loc[idx, 'TotalSignal'] = pending_signal[0]
            or_state[date_str]['trade_taken'] = True
            pending_signal = None
            continue

        # Skip if trade already taken this session
        if or_state[date_str]['trade_taken']:
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
                # OR has been identified, check for breakouts and retests

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

                # Get current state
                state = or_state[date_str]

                # Step 1: Detect initial breakout (observation only)
                if not state['breakout_detected']:
                    # Check for long breakout (close above OR_High)
                    if row['Close'] > or_high:
                        state['breakout_detected'] = True
                        state['breakout_direction'] = 'long'
                        state['breakout_time'] = idx
                        state['bars_since_breakout'] = 0

                    # Check for short breakout (close below OR_Low)
                    elif row['Close'] < or_low:
                        state['breakout_detected'] = True
                        state['breakout_direction'] = 'short'
                        state['breakout_time'] = idx
                        state['bars_since_breakout'] = 0

                # Step 2 & 3: Handle breakout state
                elif state['breakout_detected']:
                    # Increment bars since breakout
                    state['bars_since_breakout'] += 1

                    # Check timeout
                    if state['bars_since_breakout'] > entry_timeout_bars:
                        # Timeout - reset state, skip this session
                        state['breakout_detected'] = False
                        state['breakout_direction'] = None
                        state['breakout_time'] = None
                        state['bars_since_breakout'] = 0
                        state['retest_occurred'] = False
                        continue

                    # Step 2: Check for retest
                    if not state['retest_occurred']:
                        retest_occurred = False

                        if state['breakout_direction'] == 'long':
                            # Check if price returns to OR_High within tolerance
                            # Retest if Low touches OR_High (within tolerance)
                            if abs(row['Low'] - or_high) <= retest_tolerance:
                                retest_occurred = True

                        elif state['breakout_direction'] == 'short':
                            # Check if price returns to OR_Low within tolerance
                            # Retest if High touches OR_Low (within tolerance)
                            if abs(row['High'] - or_low) <= retest_tolerance:
                                retest_occurred = True

                        if retest_occurred:
                            state['retest_occurred'] = True

                            # Step 3: Check for confirmation

                            # Option B: Rejection wick confirmation (checked first as it signals immediately)
                            body = abs(row['Close'] - row['Open'])
                            upper_wick = row['High'] - max(row['Open'], row['Close'])
                            lower_wick = min(row['Open'], row['Close']) - row['Low']

                            option_b_triggered = False

                            if state['breakout_direction'] == 'long':
                                # Long: Lower wick at OR_High (bullish rejection)
                                # Check if lower wick touches OR_High within tolerance
                                if abs(row['Low'] - or_high) <= retest_tolerance:
                                    # Wick must be ≥ 2× body size
                                    if lower_wick >= 2 * body and body > 0:
                                        # Signal AT this candle close
                                        df.loc[idx, 'TotalSignal'] = SIGNAL_BUY
                                        state['trade_taken'] = True
                                        option_b_triggered = True

                            elif state['breakout_direction'] == 'short':
                                # Short: Upper wick at OR_Low (bearish rejection)
                                # Check if upper wick touches OR_Low within tolerance
                                if abs(row['High'] - or_low) <= retest_tolerance:
                                    # Wick must be ≥ 2× body size
                                    if upper_wick >= 2 * body and body > 0:
                                        # Signal AT this candle close
                                        df.loc[idx, 'TotalSignal'] = SIGNAL_SELL
                                        state['trade_taken'] = True
                                        option_b_triggered = True

                            # Option A: Candle close confirmation (only if Option B didn't trigger)
                            if not option_b_triggered:
                                if state['breakout_direction'] == 'long':
                                    # Long: Close > OR_High after touching it
                                    if row['Close'] > or_high:
                                        # Schedule signal for NEXT candle
                                        pending_signal = (SIGNAL_BUY, idx)
                                elif state['breakout_direction'] == 'short':
                                    # Short: Close < OR_Low after touching it
                                    if row['Close'] < or_low:
                                        # Schedule signal for NEXT candle
                                        pending_signal = (SIGNAL_SELL, idx)

    return df
