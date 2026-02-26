"""
Signal calculation for swing-1 support/resistance pattern strategy.

Calculates TotalSignal based on:
- Support/Resistance zone detection
- Price action patterns (candlestick patterns)
- Zone proximity filtering
"""
from typing import Optional
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# Try to import talib for pattern detection
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

from . import constants as const


def identify_support_resistance_zones(
    df: pd.DataFrame,
    current_price: Optional[float] = None,
    order: int = 5,
    zone_pct: float = const.SR_ZONE_THRESHOLD,
) -> pd.DataFrame:
    """
    Detect pivot-based support/resistance zones.

    Returns a DataFrame with columns: price, type, strength
    """
    if current_price is None:
        current_price = df["Close"].iloc[-1]

    closes = df["Close"].values
    highs_idx = argrelextrema(closes, np.greater, order=order)[0]
    lows_idx = argrelextrema(closes, np.less, order=order)[0]

    raw_zones = []
    for i in highs_idx:
        raw_zones.append({"price": closes[i], "type": "resistance", "touches": 1})
    for i in lows_idx:
        raw_zones.append({"price": closes[i], "type": "support", "touches": 1})

    raw_zones.sort(key=lambda z: z["price"])

    # Merge nearby zones
    merged = []
    for z in raw_zones:
        if merged and abs(z["price"] - merged[-1]["price"]) / merged[-1]["price"] < zone_pct:
            last = merged[-1]
            last["price"] = (last["price"] * last["touches"] + z["price"]) / (last["touches"] + 1)
            last["touches"] += 1
            if last["type"] != z["type"]:
                last["type"] = "both"
        else:
            merged.append(dict(z))

    # Filter zones by strength - more lenient (only need 1 touch)
    zones = [z for z in merged if z["touches"] >= 1 and z["type"] in ("support", "resistance")]

    return pd.DataFrame(zones)


def detect_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect candlestick patterns using talib or pandas-ta.

    Returns DataFrame with pattern columns (1=bullish, -1=bearish, 0=no pattern)
    """
    out = df.copy()

    if not HAS_TALIB:
        # Fallback: simple pattern detection without talib
        out['hammer'] = _detect_hammer(out)
        out['doji'] = _detect_doji(out)
        out['engulfing'] = _detect_engulfing(out)
        return out

    # Use talib for comprehensive pattern detection
    o = out["Open"].to_numpy().astype(float)
    h = out["High"].to_numpy().astype(float)
    l = out["Low"].to_numpy().astype(float)
    c = out["Close"].to_numpy().astype(float)
    norm = lambda raw: np.sign(raw).astype(int)

    out["doji"] = norm(talib.CDLDOJI(o, h, l, c))
    out["hammer"] = norm(talib.CDLHAMMER(o, h, l, c))
    out["inverted_hammer"] = norm(talib.CDLINVERTEDHAMMER(o, h, l, c))
    out["hanging_man"] = norm(talib.CDLHANGINGMAN(o, h, l, c))
    out["morning_star"] = norm(talib.CDLMORNINGSTAR(o, h, l, c))
    out["evening_star"] = norm(talib.CDLEVENINGSTAR(o, h, l, c))
    out["engulfing"] = norm(talib.CDLENGULFING(o, h, l, c))
    out["three_white_soldiers"] = norm(talib.CDL3WHITESOLDIERS(o, h, l, c))
    out["three_black_crows"] = norm(talib.CDL3BLACKCROWS(o, h, l, c))

    return out


def _detect_hammer(df: pd.DataFrame) -> pd.Series:
    """Simple hammer/hanging man detection. Returns 1 for bullish hammer, -1 for bearish hanging man."""
    body = abs(df['Close'] - df['Open'])
    upper_shadow = df['High'] - df[['Open', 'Close']].max(axis=1)
    lower_shadow = df[['Open', 'Close']].min(axis=1) - df['Low']
    total_range = df['High'] - df['Low']

    # Hammer/hanging man pattern: small body, long lower shadow, little/no upper shadow
    is_hammer_pattern = (
        (lower_shadow >= 1.5 * body) &
        (upper_shadow <= 0.3 * total_range) &
        (body <= 0.4 * total_range)
    )

    # Determine direction: green body = bullish (hammer), red body = bearish (hanging man)
    is_bullish = df['Close'] > df['Open']

    signal = pd.Series(0, index=df.index)
    signal[is_hammer_pattern & is_bullish] = 1  # Bullish hammer
    signal[is_hammer_pattern & ~is_bullish] = -1  # Bearish hanging man

    return signal


def _detect_doji(df: pd.DataFrame) -> pd.Series:
    """Simple doji detection."""
    body = abs(df['Close'] - df['Open'])
    total_range = df['High'] - df['Low']

    is_doji = body <= 0.1 * total_range
    return is_doji.astype(int)


def _detect_engulfing(df: pd.DataFrame) -> pd.Series:
    """Simple engulfing pattern detection."""
    # Bullish engulfing: small red candle followed by large green candle
    # Bearish engulfing: small green candle followed by large red candle

    body = df['Close'] - df['Open']
    prev_body = body.shift(1)

    # Bullish engulfing
    bullish = (
        (prev_body < 0) &  # Previous candle is red
        (body > 0) &  # Current candle is green
        (df['Close'].shift(1) > df['Open'].shift(1)) &  # Previous close > open
        (df['Open'] < df['Close'].shift(1)) &  # Current open < previous close
        (df['Close'] > df['Open'].shift(1))  # Current close > previous open
    )

    # Bearish engulfing
    bearish = (
        (prev_body > 0) &  # Previous candle is green
        (body < 0) &  # Current candle is red
        (df['Open'] > df['Close'].shift(1)) &  # Current open > previous close
        (df['Close'] < df['Open'].shift(1))  # Current close < previous open
    )

    signal = pd.Series(0, index=df.index)
    signal[bullish] = 1
    signal[bearish] = -1

    return signal


def swing_1_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """
    Calculate TotalSignal for swing-1 strategy.

    Signal values:
    - 0: No signal
    - 1: Sell signal (bearish pattern at resistance)
    - 2: Buy signal (bullish pattern at support)

    Args:
        df: DataFrame with OHLCV data
        parameters: Strategy parameters (not used, kept for consistency)

    Returns:
        DataFrame with TotalSignal column added
    """
    signals_df = df.copy()

    # Calculate ATR if not present
    if 'volatility_atr' not in signals_df.columns:
        high = signals_df['High']
        low = signals_df['Low']
        close = signals_df['Close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        signals_df['volatility_atr'] = tr.rolling(window=14).mean()

    # Drop NaN rows
    signals_df.dropna(subset=['volatility_atr'], inplace=True)

    # Add RSI for additional signal confirmation
    try:
        import pandas_ta as ta
        signals_df['RSI'] = ta.rsi(signals_df['Close'], length=14)
    except Exception:
        # Fallback RSI calculation
        delta = signals_df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        signals_df['RSI'] = 100 - (100 / (1 + rs))

    signals_df.dropna(subset=['RSI'], inplace=True)

    # Identify support/resistance zones
    zones_df = identify_support_resistance_zones(signals_df)

    # Detect candlestick patterns
    patterns_df = detect_candlestick_patterns(signals_df)

    # Calculate signals
    signals = []
    for i in range(len(signals_df)):
        current_price = signals_df['Close'].iloc[i]
        rsi_val = signals_df['RSI'].iloc[i]

        # Find nearest zone
        nearest_zone = None
        min_distance = float('inf')

        for _, zone in zones_df.iterrows():
            distance = abs(current_price - zone['price']) / zone['price']
            if distance < const.SR_PATTERN_ZONE_PROXIMITY and distance < min_distance:
                min_distance = distance
                nearest_zone = zone

        # Check for patterns at this bar
        pattern_signal = 0

        # Check various pattern columns
        pattern_cols = ['hammer', 'doji', 'engulfing']
        if HAS_TALIB:
            pattern_cols.extend(['inverted_hammer', 'hanging_man', 'morning_star',
                                'evening_star', 'three_white_soldiers', 'three_black_crows'])

        for col in pattern_cols:
            if col in patterns_df.columns:
                pattern_val = patterns_df[col].iloc[i]
                if pattern_val != 0:
                    pattern_signal = pattern_val
                    break

        # Generate signal based on multiple factors
        signal = 0

        # Pattern + Zone combination (highest priority)
        if nearest_zone is not None:
            if pattern_signal == 1 and nearest_zone['type'] == 'support':
                signal = 2  # Buy signal
            elif pattern_signal == -1 and nearest_zone['type'] == 'resistance':
                signal = 1  # Sell signal
            # Fallback: RSI + Zone combination
            elif rsi_val < 40 and nearest_zone['type'] == 'support':
                signal = 2  # Buy signal
            elif rsi_val > 60 and nearest_zone['type'] == 'resistance':
                signal = 1  # Sell signal
        else:
            # No zone nearby, use RSI only
            if rsi_val < 30:
                signal = 2  # Buy signal (oversold)
            elif rsi_val > 70:
                signal = 1  # Sell signal (overbought)

        signals.append(signal)

    # Ensure signals length matches dataframe
    signals_df['TotalSignal'] = signals

    return signals_df
