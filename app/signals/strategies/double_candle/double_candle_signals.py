"""
Double Candle Strategy Signals

Buy Signal: Generated when 2 consecutive green candles appear
Sell Signal: Generated when 2 consecutive red candles appear

Green candle: Close > Open
Red candle: Close < Open

Position sizing rules:
- Base size: 0.03 (3% of account)
- Dynamic sizing based on ATR volatility
- Lower volatility = larger position (more confidence)
- Higher volatility = smaller position (less risk)
- Size range: 0.01 to 0.05
"""
import pandas as pd
import numpy as np


def double_candle_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """
    Calculate TotalSignal for double candle strategy.

    Signal values:
    - 0: No signal
    - 1: Sell signal (2 consecutive red candles)
    - 2: Buy signal (2 consecutive green candles)

    Args:
        df: DataFrame with OHLCV data
        parameters: Strategy parameters (optional, for future extensibility)

    Returns:
        DataFrame with TotalSignal column added
    """
    signals_df = df.copy()

    # Calculate candle colors
    # Green candle: Close > Open (1)
    # Red candle: Close < Open (-1)
    # Doji/neutral: Close == Open (0)
    signals_df['candle_color'] = np.sign(signals_df['Close'] - signals_df['Open']).astype(int)

    # Calculate ATR for volatility-based position sizing
    try:
        import pandas_ta as ta
        signals_df['volatility_atr'] = ta.atr(
            high=signals_df['High'],
            low=signals_df['Low'],
            close=signals_df['Close'],
            length=14
        )
    except Exception:
        # Fallback ATR calculation
        high = signals_df['High']
        low = signals_df['Low']
        close = signals_df['Close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        signals_df['volatility_atr'] = tr.rolling(window=14).mean()

    # Calculate position size based on volatility (ATR % of price)
    # Lower ATR % = larger position, Higher ATR % = smaller position
    signals_df['atr_pct'] = signals_df['volatility_atr'] / signals_df['Close']

    # Dynamic position sizing
    # Base size 0.03, adjusted by volatility
    # ATR% < 1%: increase size (low volatility = more confidence)
    # ATR% > 2%: decrease size (high volatility = less risk)
    def calculate_position_size(atr_pct):
        if atr_pct < 0.01:
            return min(0.05, 0.03 + (0.01 - atr_pct) * 2)  # Max 0.05
        elif atr_pct > 0.02:
            return max(0.01, 0.03 - (atr_pct - 0.02) * 1)  # Min 0.01
        else:
            return 0.03  # Base size

    signals_df['position_size'] = signals_df['atr_pct'].apply(calculate_position_size)

    # Calculate 2-consecutive candle patterns
    signals_df['prev_candle'] = signals_df['candle_color'].shift(1)

    # Initialize signals
    signals = [0] * len(signals_df)

    # Generate signals starting from index 1 (need previous candle)
    for i in range(1, len(signals_df)):
        current = signals_df['candle_color'].iloc[i]
        previous = signals_df['prev_candle'].iloc[i]

        # Buy signal: 2 consecutive green candles (both == 1)
        if current == 1 and previous == 1:
            signals[i] = 2
        # Sell signal: 2 consecutive red candles (both == -1)
        elif current == -1 and previous == -1:
            signals[i] = 1
        else:
            signals[i] = 0

    signals_df['TotalSignal'] = signals

    # Drop rows with NaN values from ATR calculation
    signals_df.dropna(subset=['volatility_atr'], inplace=True)

    return signals_df
