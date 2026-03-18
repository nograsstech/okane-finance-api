"""
Mean Reversion + Trend Filter Strategy Signals

Combines mean reversion entries with higher-timeframe trend filtering.
- 4H EMA 200 determines trend direction
- Entry timeframe (can be 15m, 1H, etc.) pullback detection
- RSI confirms pullback depth
- ATR sizes stops and targets
- VWAP acts as price anchor
- Candle patterns trigger entries

Signal values:
- 0: No signal
- 1: Sell signal
- 2: Buy signal
"""
import pandas as pd
import numpy as np


def is_bullish_engulfing(df: pd.DataFrame, i: int) -> bool:
    """
    Detect bullish engulfing candle pattern at index i.

    Bullish engulfing:
    - Previous candle is bearish (Close < Open)
    - Current candle is bullish (Close > Open)
    - Current Open < Previous Close
    - Current Close > Previous Open

    Args:
        df: DataFrame with OHLC data
        i: Index to check

    Returns:
        True if bullish engulfing pattern detected
    """
    if i < 1:
        return False

    curr = df.iloc[i]
    prev = df.iloc[i - 1]

    # Previous candle must be bearish
    if prev['Close'] >= prev['Open']:
        return False

    # Current candle must be bullish
    if curr['Close'] <= curr['Open']:
        return False

    # Current body must engulf previous body
    return (curr['Open'] < prev['Close'] and
            curr['Close'] > prev['Open'])


def is_bearish_engulfing(df: pd.DataFrame, i: int) -> bool:
    """
    Detect bearish engulfing candle pattern at index i.

    Bearish engulfing:
    - Previous candle is bullish (Close > Open)
    - Current candle is bearish (Close < Open)
    - Current Open > Previous Close
    - Current Close < Previous Open

    Args:
        df: DataFrame with OHLC data
        i: Index to check

    Returns:
        True if bearish engulfing pattern detected
    """
    if i < 1:
        return False

    curr = df.iloc[i]
    prev = df.iloc[i - 1]

    # Previous candle must be bullish
    if prev['Close'] <= prev['Open']:
        return False

    # Current candle must be bearish
    if curr['Close'] >= curr['Open']:
        return False

    # Current body must engulf previous body
    return (curr['Open'] > prev['Close'] and
            curr['Close'] < prev['Open'])


def is_hammer(df: pd.DataFrame, i: int) -> bool:
    """
    Detect hammer candle pattern at index i.

    Hammer:
    - Upper wick is small or non-existent
    - Lower wick is at least 2x the body
    - Body is in the upper portion of the candle
    - Can be bullish or bearish body (preferably bullish)

    Args:
        df: DataFrame with OHLC data
        i: Index to check

    Returns:
        True if hammer pattern detected
    """
    if i < 1:
        return False

    curr = df.iloc[i]

    body = abs(curr['Close'] - curr['Open'])
    upper_wick = curr['High'] - max(curr['Open'], curr['Close'])
    lower_wick = min(curr['Open'], curr['Close']) - curr['Low']
    total_range = curr['High'] - curr['Low']

    # Avoid division by zero
    if total_range == 0:
        return False

    # Lower wick must be at least 2x the body
    if lower_wick < body * 2:
        return False

    # Upper wick should be small (less than 1/3 of total range)
    if upper_wick > total_range / 3:
        return False

    # Body should be in upper portion (lower wick > upper wick + body)
    return lower_wick > upper_wick + body


def is_shooting_star(df: pd.DataFrame, i: int) -> bool:
    """
    Detect shooting star candle pattern at index i.

    Shooting star:
    - Lower wick is small or non-existent
    - Upper wick is at least 2x the body
    - Body is in the lower portion of the candle
    - Can be bullish or bearish body (preferably bearish)

    Args:
        df: DataFrame with OHLC data
        i: Index to check

    Returns:
        True if shooting star pattern detected
    """
    if i < 1:
        return False

    curr = df.iloc[i]

    body = abs(curr['Close'] - curr['Open'])
    upper_wick = curr['High'] - max(curr['Open'], curr['Close'])
    lower_wick = min(curr['Open'], curr['Close']) - curr['Low']
    total_range = curr['High'] - curr['Low']

    # Avoid division by zero
    if total_range == 0:
        return False

    # Upper wick must be at least 2x the body
    if upper_wick < body * 2:
        return False

    # Lower wick should be small (less than 1/3 of total range)
    if lower_wick > total_range / 3:
        return False

    # Body should be in lower portion (upper wick > lower wick + body)
    return upper_wick > lower_wick + body


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Volume Weighted Average Price (VWAP).

    VWAP = Cumulative(Price * Volume) / Cumulative(Volume)
    Uses typical price: (High + Low + Close) / 3

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Series with VWAP values
    """
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    cumulative_tp_volume = (typical_price * df['Volume']).cumsum()
    cumulative_volume = df['Volume'].cumsum()

    return cumulative_tp_volume / cumulative_volume


def detect_timeframe(df: pd.DataFrame) -> str:
    """
    Detect the timeframe of the DataFrame based on index frequency.

    Args:
        df: DataFrame with DatetimeIndex

    Returns:
        Detected timeframe string (e.g., '15min', '1h', '4h', '1d')
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    if len(df) < 2:
        return '1h'  # Default assumption

    # Calculate the mode of time differences
    time_diffs = df.index.to_series().diff().dropna()
    if len(time_diffs) == 0:
        return '1h'

    # Get the most common time difference
    mode_diff = time_diffs.mode()
    if len(mode_diff) > 0:
        median_diff = mode_diff.iloc[0]
    else:
        median_diff = time_diffs.median()

    # Map time difference to timeframe
    if median_diff <= pd.Timedelta(minutes=30):
        return '15min'
    elif median_diff <= pd.Timedelta(hours=2):
        return '1h'
    elif median_diff <= pd.Timedelta(hours=8):
        return '4h'
    else:
        return '1d'


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample data to 4H timeframe, regardless of input timeframe.

    Args:
        df: DataFrame with OHLCV data (any timeframe)

    Returns:
        4H resampled DataFrame
    """
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Resample to 4H
    resampled = df.resample('4h').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    return resampled


def merge_trend_to_entry_timeframe(df_entry: pd.DataFrame, df_trend: pd.DataFrame) -> pd.DataFrame:
    """
    Merge higher timeframe trend indicator to entry timeframe using forward fill.

    This properly aligns timestamps across different timeframes by using
    reindex with forward fill after ensuring both indexes are timezone-aware.

    Args:
        df_entry: Entry timeframe DataFrame (e.g., 15m, 1H)
        df_trend: Trend timeframe DataFrame (e.g., 4H)

    Returns:
        df_entry with additional EMA_100_4H, EMA_200_4H, and Close_4H columns
    """
    # Ensure both indexes are datetime
    if not isinstance(df_entry.index, pd.DatetimeIndex):
        df_entry.index = pd.to_datetime(df_entry.index)
    if not isinstance(df_trend.index, pd.DatetimeIndex):
        df_trend.index = pd.to_datetime(df_trend.index)

    # Create a series from the 4H EMAs and forward fill them to the entry timeframe
    ema_100_4h_series = df_trend['EMA_100'].reindex(
        df_entry.index.union(df_trend.index),
        method='ffill'
    )
    ema_200_4h_series = df_trend.get('EMA_200', pd.Series(dtype=float)).reindex(
        df_entry.index.union(df_trend.index),
        method='ffill'
    )
    close_4h_series = df_trend['Close'].reindex(
        df_entry.index.union(df_trend.index),
        method='ffill'
    )

    # Align to entry timeframe index
    df_entry['EMA_100_4H'] = ema_100_4h_series.loc[df_entry.index]
    df_entry['EMA_200_4H'] = ema_200_4h_series.loc[df_entry.index]
    df_entry['Close_4H'] = close_4h_series.loc[df_entry.index]

    return df_entry


def mean_reversion_trend_filter_signals(df_1h: pd.DataFrame, df_4h: pd.DataFrame = None, parameters: dict = None) -> pd.DataFrame:
    """
    Calculate TotalSignal for mean reversion + trend filter strategy.

    This strategy combines:
    - 4H trend filter (price vs EMA 200)
    - Entry timeframe pullback detection (price near EMA 50)
    - RSI confirmation
    - VWAP alignment
    - Candle pattern triggers

    The function handles any input timeframe (15m, 1H, etc.) by resampling
    to 4H for trend filtering.

    Args:
        df_1h: Entry timeframe DataFrame with OHLCV data (can be any timeframe)
        df_4h: 4H timeframe DataFrame with OHLCV data (optional, will be resampled if not provided)
        parameters: Strategy parameters dict (optional)

    Returns:
        DataFrame with TotalSignal column added (0=none, 1=sell, 2=buy)
    """
    if df_1h is None or df_1h.empty:
        print("mean_reversion_trend_filter_signals: df is None or empty")
        return None

    # Create working copy
    df = df_1h.copy()

    # Handle MultiIndex columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        # Flatten MultiIndex columns - take the first level (Open, High, Low, Close, Volume)
        df.columns = df.columns.get_level_values(0)

    # Ensure we have the required columns
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"mean_reversion_trend_filter_signals: Missing columns: {missing_cols}. Available: {df.columns.tolist()}")
        return None

    # Ensure we have enough data for the indicators
    min_rows = 1000  # Minimum rows needed for meaningful analysis
    if len(df) < min_rows:
        print(f"mean_reversion_trend_filter_signals: Insufficient data ({len(df)} rows, need at least {min_rows})")
        # Return the dataframe with no signals rather than None
        df['TotalSignal'] = 0
        return df

    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Resample to 4H if not provided
    if df_4h is None or df_4h.empty:
        df_4h = resample_to_4h(df)
    else:
        df_4h = df_4h.copy()
        if not isinstance(df_4h.index, pd.DatetimeIndex):
            df_4h.index = pd.to_datetime(df_4h.index)

    # Check if we have enough 4H data for EMA 100 (faster than EMA 200)
    if len(df_4h) < 100:
        print(f"mean_reversion_trend_filter_signals: Insufficient 4H data ({len(df_4h)} rows, need at least 100 for EMA 100)")
        # Fall back to using entry timeframe for trend
        df_4h = df

    # Calculate indicators on 4H data for trend filter
    try:
        import pandas_ta as ta

        # 4H indicators - EMA 100 for faster trend detection (2x faster than EMA 200)
        df_4h['EMA_100'] = ta.ema(df_4h['Close'], length=100)
        df_4h['EMA_200'] = ta.ema(df_4h['Close'], length=200)  # Keep for reference

        # Entry timeframe indicators - also add EMA 100 for even faster reaction
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_100'] = ta.ema(df['Close'], length=100)
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    except ImportError:
        # Fallback if pandas_ta not available
        print("Warning: pandas_ta not available, using manual calculations")
        # Simple EMA calculation
        def ema(series, length):
            return series.ewm(span=length, adjust=False).mean()

        df_4h['EMA_100'] = ema(df_4h['Close'], 100)
        df_4h['EMA_200'] = ema(df_4h['Close'], 200)
        df['EMA_50'] = ema(df['Close'], 50)
        df['EMA_100'] = ema(df['Close'], 100)
        df['EMA_200'] = ema(df['Close'], 200)

        # Manual RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # Manual ATR
        high = df['High']
        low = df['Low']
        close = df['Close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(window=14).mean()

    # Calculate VWAP on entry timeframe data
    df['VWAP'] = calculate_vwap(df)

    # Check if VWAP is usable (has valid values, not all NaN)
    # This handles Forex pairs where yfinance returns zero volume
    vwap_usable = df['VWAP'].notna().sum() > len(df) * 0.5  # At least 50% valid
    if not vwap_usable:
        print("mean_reversion_trend_filter_signals: VWAP not usable (likely zero volume data), disabling VWAP filter")

    # Merge 4H trend indicator to entry timeframe
    df = merge_trend_to_entry_timeframe(df, df_4h)

    # Calculate distance from EMA 50 as percentage of ATR
    df['ema_50_distance'] = (df['Close'] - df['EMA_50']).abs()
    # Tightened pullback zone: 1.0x ATR for higher quality entries
    df['near_ema_50'] = df['ema_50_distance'] <= (df['ATR'] * 1.0)
    # Minimum distance requirement to avoid entries too close to EMA 50
    df['far_enough_from_ema50'] = df['ema_50_distance'] >= (df['ATR'] * 0.3)

    # ATR percentile filter to detect high volatility periods
    df['atr_percentile'] = df['ATR'].rolling(100, min_periods=50).rank(pct=True)

    # TREND STRENGTH FILTER: Calculate 4H distance from EMA 100 as % of ATR
    # Using EMA 100 instead of EMA 200 for faster trend reaction
    df['trend_strength_4h'] = (df['Close_4H'] - df['EMA_100_4H']).abs() / df['ATR']
    # Strong trend = price is at least 0.5x ATR away from EMA 100
    df['strong_uptrend'] = (df['Close_4H'] > df['EMA_100_4H']) & (df['trend_strength_4h'] >= 0.5)
    df['strong_downtrend'] = (df['Close_4H'] < df['EMA_100_4H']) & (df['trend_strength_4h'] >= 0.5)

    # TREND CHANGE DETECTION: Detect when 4H price crosses EMA 100 (faster than EMA 200)
    df['trend_up_4h'] = df['Close_4H'] > df['EMA_100_4H']
    prev_trend_up = df['trend_up_4h'].shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    df['trend_change_to_up'] = (df['trend_up_4h'].astype(bool) & ~prev_trend_up)
    df['trend_change_to_down'] = (~df['trend_up_4h'].astype(bool) & prev_trend_up)

    # Trend change cooldown (skip signals for N bars after trend change)
    trend_change_bars = 20  # Skip signals for 20 bars after trend change (~5 hours on 15m)
    df['trend_change_cooldown'] = False
    for i in range(len(df)):
        if df['trend_change_to_up'].iloc[i] or df['trend_change_to_down'].iloc[i]:
            # Set cooldown for next N bars
            end_idx = min(i + trend_change_bars, len(df))
            df.loc[df.index[i:end_idx], 'trend_change_cooldown'] = True

    # Detect price crossing above/below EMA 50 (alternative pullback signal)
    df['price_above_ema50'] = df['Close'] > df['EMA_50'].astype(float)
    prev_above = df['price_above_ema50'].shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    df['ema50_cross_up'] = (df['price_above_ema50'].astype(bool) & ~prev_above)
    df['ema50_cross_down'] = (~df['price_above_ema50'].astype(bool) & prev_above)

    # ENTRY TIMEFRAME TREND FILTER - Detects trend changes faster than 4H EMA 200
    # Calculate EMA 50 slope (rising = bullish, falling = bearish)
    df['ema50_slope'] = df['EMA_50'].diff(5)  # 5-period slope
    df['ema50_rising'] = df['ema50_slope'] > 0
    df['ema50_falling'] = df['ema50_slope'] < 0

    # Price position relative to EMA 50 on entry timeframe
    df['price_far_above_ema50'] = (df['Close'] - df['EMA_50']) > (df['ATR'] * 0.5)
    df['price_far_below_ema50'] = (df['EMA_50'] - df['Close']) > (df['ATR'] * 0.5)

    # Detect momentum: price closing higher/lower than previous candle
    df['bullish_momentum'] = df['Close'] > df['Close'].shift(1)
    df['bearish_momentum'] = df['Close'] < df['Close'].shift(1)

    # Initialize signals array
    signals = [0] * len(df)

    # Generate signals starting from index where all indicators are available
    start_idx = max(50, 14, 2)  # Minimum periods for indicators

    for i in range(start_idx, len(df)):
        # Skip if any required indicator is NaN
        # VWAP is optional - skip check if not usable
        required_na_check = [
            pd.isna(df['EMA_100_4H'].iloc[i]),
            pd.isna(df['Close_4H'].iloc[i]),
            pd.isna(df['EMA_50'].iloc[i]),
            pd.isna(df['RSI'].iloc[i]),
            pd.isna(df['ATR'].iloc[i]),
        ]
        if vwap_usable:
            required_na_check.append(pd.isna(df['VWAP'].iloc[i]))

        if any(required_na_check):
            continue

        # Check candle patterns
        bullish_pattern = (is_bullish_engulfing(df, i) or is_hammer(df, i))
        bearish_pattern = (is_bearish_engulfing(df, i) or is_shooting_star(df, i))

        # PRIMARY TREND FILTER: Entry timeframe EMA 100 (fastest reaction)
        # Using entry timeframe EMA 100 as primary since it reacts to trend changes much faster than 4H
        entry_tf_above_ema100 = df['Close'].iloc[i] > df['EMA_100'].iloc[i]
        entry_tf_below_ema100 = df['Close'].iloc[i] < df['EMA_100'].iloc[i]

        # SECONDARY TREND FILTER: 4H EMA 100 (slower confirmation)
        uptrend_4h = df['strong_uptrend'].iloc[i]
        downtrend_4h = df['strong_downtrend'].iloc[i]

        # ENTRY TIMEFRAME MOMENTUM CHECK - Skip if price is moving against intended direction
        entry_tf_bearish = (
            df['price_far_below_ema50'].iloc[i] or  # Price well below EMA 50
            df['ema50_falling'].iloc[i]  # EMA 50 slope falling
        )
        entry_tf_bullish = (
            df['price_far_above_ema50'].iloc[i] or  # Price well above EMA 50
            df['ema50_rising'].iloc[i]  # EMA 50 slope rising
        )

        # COMBINED TREND CHECK: Entry timeframe EMA 100 is PRIMARY, 4H is secondary confirmation
        # Long requires: Price > EMA 100 (entry TF) AND (4H uptrend OR not 4H downtrend)
        uptrend = entry_tf_above_ema100 and (uptrend_4h or not downtrend_4h) and not entry_tf_bearish
        # Short requires: Price < EMA 100 (entry TF) AND (4H downtrend OR not 4H uptrend)
        downtrend = entry_tf_below_ema100 and (downtrend_4h or not uptrend_4h) and not entry_tf_bullish

        # Skip signals if we're in a trend change cooldown period
        if df['trend_change_cooldown'].iloc[i]:
            signals[i] = 0
            continue

        # Pullback detection: near EMA 50 OR just crossed it
        pullback_long = (df['near_ema_50'].iloc[i] or df['ema50_cross_up'].iloc[i])
        pullback_short = (df['near_ema_50'].iloc[i] or df['ema50_cross_down'].iloc[i])

        # Skip if ATR is in top 5% (only extreme volatility spikes)
        extreme_volatility = df['atr_percentile'].iloc[i] > 0.95

        # Balanced RSI zones - tighter than original but not too restrictive
        rsi_oversold = 30 <= df['RSI'].iloc[i] <= 50  # Middle ground
        rsi_overbought = 50 <= df['RSI'].iloc[i] <= 70  # Middle ground

        # VWAP condition (skip if VWAP not usable - common for Forex pairs)
        vwap_long_ok = not vwap_usable or df['Close'].iloc[i] >= df['VWAP'].iloc[i]
        vwap_short_ok = not vwap_usable or df['Close'].iloc[i] <= df['VWAP'].iloc[i]

        # STRONG SIGNALS (with candle pattern confirmation)
        strong_long = (
            uptrend and
            pullback_long and
            rsi_oversold and
            vwap_long_ok and
            bullish_pattern and
            not extreme_volatility
        )

        strong_short = (
            downtrend and
            pullback_short and
            rsi_overbought and
            vwap_short_ok and
            bearish_pattern and
            not extreme_volatility
        )

        # STANDARD SIGNALS (with stronger momentum - 2 consecutive bullish/bearish candles)
        strong_momentum_long = (
            df['bullish_momentum'].iloc[i] and
            df['bullish_momentum'].iloc[i-1] if i > 0 else False
        )
        strong_momentum_short = (
            df['bearish_momentum'].iloc[i] and
            df['bearish_momentum'].iloc[i-1] if i > 0 else False
        )

        standard_long = (
            uptrend and
            pullback_long and
            rsi_oversold and
            vwap_long_ok and
            strong_momentum_long and
            not bullish_pattern and
            not extreme_volatility
        )

        standard_short = (
            downtrend and
            pullback_short and
            rsi_overbought and
            vwap_short_ok and
            strong_momentum_short and
            not bearish_pattern and
            not extreme_volatility
        )

        # SIGNAL GENERATION (strong first, then standard)
        if strong_long:
            signals[i] = 2
        elif strong_short:
            signals[i] = 1
        elif standard_long:
            signals[i] = 2
        elif standard_short:
            signals[i] = 1
        else:
            signals[i] = 0

    df['TotalSignal'] = signals

    # Drop only rows where essential backtest columns are NaN
    # Keep rows with signals even if some auxiliary indicators are NaN
    df.dropna(subset=['TotalSignal', 'Close', 'High', 'Low', 'Open', 'Volume', 'ATR'], inplace=True)

    # If DataFrame is empty after dropna, return original with zeros
    if df.empty:
        print("mean_reversion_trend_filter_signals: DataFrame empty after dropna, returning original with no signals")
        df = df_1h.copy()
        df['TotalSignal'] = 0

    return df
