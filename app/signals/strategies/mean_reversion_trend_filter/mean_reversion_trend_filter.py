"""
Signal calculation for Mean Reversion + Trend Filter Combo Strategy.

This strategy combines:
- Multi-timeframe trend analysis (4H EMA 200 trend filter)
- Pullback detection (50 EMA + RSI zones)
- Daily VWAP as institutional price anchor
- Candle pattern triggers (engulfing, hammer, shooting star)
- ATR-based risk management

Signal values:
- 0: No signal
- 1: Sell signal (short)
- 2: Buy signal (long)
"""

import pandas as pd
import pandas_ta as ta
import numpy as np


def calculate_daily_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate VWAP reset daily for intraday data.

    VWAP = Volume-Weighted Average Price
    Resets at the start of each trading day.

    Note: For forex pairs without volume data, uses typical price (HLC/3)
    as a proxy instead of VWAP.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with VWAP column added
    """
    df = df.copy()

    # Check if volume data is available (not all zeros)
    has_volume = df['Volume'].max() > 0

    if not has_volume:
        # For forex pairs without volume, use typical price as VWAP proxy
        # This is a daily average of the HLC typical price
        df['Date'] = df.index.date
        df['typical_price'] = (df.High + df.Low + df.Close) / 3

        # Calculate daily average of typical price (expanding mean)
        df['VWAP'] = df.groupby('Date')['typical_price'].transform(
            lambda x: x.expanding().mean()
        )

        df.drop(['Date', 'typical_price'], axis=1, inplace=True)
    else:
        # Standard VWAP calculation with volume
        df['Date'] = df.index.date
        df['typical_price'] = (df.High + df.Low + df.Close) / 3
        df['pv'] = df.typical_price * df.Volume

        # Calculate cumulative PV and cumulative Volume per day
        df['cum_pv'] = df.groupby('Date')['pv'].cumsum()
        df['cum_volume'] = df.groupby('Date')['Volume'].cumsum()

        # VWAP = cumulative PV / cumulative Volume
        df['VWAP'] = df['cum_pv'] / df['cum_volume']

        # Clean up temporary columns
        df.drop(['typical_price', 'pv', 'cum_pv', 'cum_volume'], axis=1, inplace=True)

    return df


def detect_engulfing(df: pd.DataFrame) -> pd.Series:
    """
    Detect engulfing candle patterns.

    Returns:
        Series with 1 (bullish engulfing), -1 (bearish engulfing), 0 (none)
    """
    body = df['Close'] - df['Open']
    prev_body = body.shift(1)

    # Bullish engulfing: small red candle followed by large green candle
    bullish = (
        (prev_body < 0) &  # Previous candle is red
        (body > 0) &  # Current candle is green
        (df['Open'] < df['Close'].shift(1)) &  # Current open < previous close
        (df['Close'] > df['Open'].shift(1))  # Current close > previous open
    )

    # Bearish engulfing: small green candle followed by large red candle
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


def detect_hammer(df: pd.DataFrame) -> pd.Series:
    """
    Detect hammer and shooting star patterns.

    Hammer: small body, long lower shadow, little/no upper shadow (bullish)
    Shooting star: small body, long upper shadow, little/no lower shadow (bearish)

    Returns:
        Series with 1 (hammer), -1 (shooting star), 0 (none)
    """
    body = abs(df['Close'] - df['Open'])
    upper_shadow = df['High'] - df[['Open', 'Close']].max(axis=1)
    lower_shadow = df[['Open', 'Close']].min(axis=1) - df['Low']
    total_range = df['High'] - df['Low']

    # Hammer/hanging man pattern
    is_hammer = (
        (lower_shadow >= 1.5 * body) &
        (upper_shadow <= 0.3 * total_range) &
        (body <= 0.4 * total_range)
    )

    # Shooting star pattern
    is_shooting_star = (
        (upper_shadow >= 1.5 * body) &
        (lower_shadow <= 0.3 * total_range) &
        (body <= 0.4 * total_range)
    )

    # Determine direction based on candle color
    is_bullish = df['Close'] > df['Open']

    signal = pd.Series(0, index=df.index)
    signal[is_hammer & is_bullish] = 1  # Bullish hammer
    signal[is_hammer & ~is_bullish] = -1  # Bearish hanging man
    signal[is_shooting_star] = -1  # Shooting star is always bearish

    return signal


def merge_higher_timeframe_trend(df: pd.DataFrame, df_htf: pd.DataFrame) -> pd.DataFrame:
    """
    Merge higher timeframe (4H) trend data into entry timeframe.

    Uses date-based merging to align 4H EMA 200 values with 15M/1H candles.

    Args:
        df: Entry timeframe DataFrame (15M or 1H)
        df_htf: Higher timeframe DataFrame (4H)

    Returns:
        DataFrame with EMA_200_4H column added
    """
    df = df.copy()
    df_htf = df_htf.copy()

    # Create date columns for merging
    df['Date'] = pd.to_datetime(df.index.date)
    df_htf.index = pd.to_datetime(df_htf.index)
    df_htf['Date'] = df_htf.index.date

    # Drop rows where EMA_200 is NaN (warmup period)
    df_htf_valid = df_htf.dropna(subset=['EMA_200'])

    # Create mapping from date to EMA_200 value (only use valid EMA values)
    date_to_ema = df_htf_valid.groupby('Date')['EMA_200'].last().to_dict()

    # Map EMA values to entry timeframe
    df['EMA_200_4H'] = df['Date'].map(date_to_ema)

    # Forward fill to carry values forward
    df['EMA_200_4H'] = df['EMA_200_4H'].ffill()

    return df


def mean_reversion_trend_filter_signals(
    df: pd.DataFrame,
    df_htf: pd.DataFrame,
    parameters: dict
) -> pd.DataFrame:
    """
    Calculate TotalSignal for Mean Reversion + Trend Filter strategy.

    Strategy Logic:
    - Long: 4H uptrend + price near 50 EMA + RSI 35-50 + above VWAP + bullish candle
    - Short: 4H downtrend + price near 50 EMA + RSI 50-65 + below VWAP + bearish candle

    Args:
        df: Entry timeframe DataFrame (15M or 1H) with OHLCV data
        df_htf: Higher timeframe DataFrame (4H) for trend filter
        parameters: Dict with strategy parameters

    Returns:
        DataFrame with TotalSignal column (0=none, 1=sell, 2=buy)
    """
    # Extract parameters with defaults
    ema_period_50 = parameters.get('ema_period_50', 50)
    ema_period_200 = parameters.get('ema_period_200', 200)
    rsi_period = parameters.get('rsi_period', 14)
    atr_period = parameters.get('atr_period', 14)
    pullback_atr_multiplier = parameters.get('pullback_atr_multiplier', 1.0)

    rsi_long_min = parameters.get('rsi_long_min', 35)
    rsi_long_max = parameters.get('rsi_long_max', 50)
    rsi_short_min = parameters.get('rsi_short_min', 50)
    rsi_short_max = parameters.get('rsi_short_max', 65)

    # Session filtering parameters
    session_filter = parameters.get('session_filter', False)
    session_start = parameters.get('session_start', 8)
    session_end = parameters.get('session_end', 11)

    # Invalidation parameters
    atr_volatility_period = parameters.get('atr_volatility_period', 20)
    atr_volatility_multiplier = parameters.get('atr_volatility_multiplier', 2.0)
    gap_atr_multiplier = parameters.get('gap_atr_multiplier', 1.0)

    df = df.copy()
    df_htf = df_htf.copy()

    # ========== Entry Timeframe Indicators ==========

    # Calculate EMAs
    df['EMA_50'] = ta.ema(df.Close, length=ema_period_50)
    df['EMA_200'] = ta.ema(df.Close, length=ema_period_200)

    # Calculate RSI
    df['RSI'] = ta.rsi(df.Close, length=rsi_period)

    # Calculate ATR
    df['ATR'] = ta.atr(df.High, df.Low, df.Close, length=atr_period)

    # Calculate Daily VWAP
    df = calculate_daily_vwap(df)

    # ========== Higher Timeframe Indicators ==========

    # Calculate 4H EMA 200 for trend filter
    df_htf['EMA_200'] = ta.ema(df_htf.Close, length=ema_period_200)

    # Merge 4H trend data
    df = merge_higher_timeframe_trend(df, df_htf)

    # ========== Candle Pattern Detection ==========

    df['engulfing'] = detect_engulfing(df)
    df['hammer_shooting_star'] = detect_hammer(df)

    # ========== Session Filter (Optional) ==========

    if session_filter:
        df['hour'] = df.index.hour
        df['in_session'] = (df['hour'] >= session_start) & (df['hour'] <= session_end)
    else:
        df['in_session'] = True  # No filtering

    # ========== Invalidation Checks ==========

    # ATR volatility check
    df['atr_avg'] = df['ATR'].rolling(window=atr_volatility_period).mean()
    df['volatility_ok'] = df['ATR'] <= (df['atr_avg'] * atr_volatility_multiplier)

    # Gap detection
    df['prev_close'] = df['Close'].shift(1)
    df['gap_size'] = abs(df['Open'] - df['prev_close'])
    df['gap_ok'] = df['gap_size'] <= (df['ATR'] * gap_atr_multiplier)

    # ========== Signal Conditions ==========

    # Pullback to 50 EMA condition
    df['dist_to_ema50'] = abs(df.Close - df.EMA_50)
    df['near_ema50'] = df['dist_to_ema50'] <= (df.ATR * pullback_atr_multiplier)

    # Trend filter conditions
    df['htf_trend_up'] = df.Close > df.EMA_200_4H
    df['htf_trend_down'] = df.Close < df.EMA_200_4H

    # RSI pullback zones
    df['rsi_long_zone'] = df.RSI.between(rsi_long_min, rsi_long_max)
    df['rsi_short_zone'] = df.RSI.between(rsi_short_min, rsi_short_max)

    # VWAP filter
    df['above_vwap'] = df.Close >= df.VWAP
    df['below_vwap'] = df.Close <= df.VWAP

    # Candle triggers
    df['bullish_candle'] = df['engulfing'] == 1
    df['bearish_candle'] = (df['engulfing'] == -1) | (df['hammer_shooting_star'] == -1)

    # ========== Generate Signals ==========

    # Long signal conditions
    long_conditions = (
        df['htf_trend_up'] &           # 4H uptrend
        df['near_ema50'] &              # Pullback to 50 EMA
        df['rsi_long_zone'] &           # RSI in pullback zone (35-50)
        df['above_vwap'] &              # Above VWAP (institutional support)
        df['bullish_candle'] &          # Bullish candle trigger
        df['in_session'] &              # Within session hours (if enabled)
        df['volatility_ok'] &           # ATR not too high
        df['gap_ok']                    # No excessive gap
    )

    # Short signal conditions
    short_conditions = (
        df['htf_trend_down'] &         # 4H downtrend
        df['near_ema50'] &              # Pullback to 50 EMA
        df['rsi_short_zone'] &          # RSI in pullback zone (50-65)
        df['below_vwap'] &              # Below VWAP (institutional resistance)
        df['bearish_candle'] &          # Bearish candle trigger
        df['in_session'] &              # Within session hours (if enabled)
        df['volatility_ok'] &           # ATR not too high
        df['gap_ok']                    # No excessive gap
    )

    # Initialize TotalSignal
    df['TotalSignal'] = 0

    # Apply signals
    df.loc[long_conditions, 'TotalSignal'] = 2   # Buy signal
    df.loc[short_conditions, 'TotalSignal'] = 1  # Sell signal

    # Clean up temporary columns
    cols_to_drop = [
        'Date', 'dist_to_ema50', 'near_ema50', 'htf_trend_up', 'htf_trend_down',
        'rsi_long_zone', 'rsi_short_zone', 'above_vwap', 'below_vwap',
        'bullish_candle', 'bearish_candle', 'engulfing', 'hammer_shooting_star',
        'volatility_ok', 'gap_ok', 'atr_avg', 'prev_close', 'gap_size'
    ]

    if session_filter:
        cols_to_drop.extend(['hour', 'in_session'])
    else:
        cols_to_drop.append('in_session')

    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

    # Drop rows with NaN values (from indicator warmup)
    df.dropna(inplace=True)

    return df
