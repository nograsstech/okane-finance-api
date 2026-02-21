import pandas_ta as ta
import numpy as np

def super_safe_strategy_signals(df, parameters):
    # Make a copy to avoid warnings
    df = df.copy()

    # Default parameters if not provided
    atr_length = parameters.get('atr_length', 14)
    rsi_length = parameters.get('rsi_length', 14)
    ema_short = parameters.get('ema_short', 8)
    ema_medium = parameters.get('ema_medium', 21)
    ema_long = parameters.get('ema_long', 50)
    bb_length = parameters.get('bb_length', 20)
    bb_std = parameters.get('bb_std', 2.0)
    adx_length = parameters.get('adx_length', 14)
    consolidation_threshold = parameters.get('consolidation_threshold', 0.05)  # 5% BB Width


    # Calculate indicators
    # Trend indicators (using .ta accessor for clarity)
    df['EMA_short'] = ta.ema(df.Close, length=ema_short)
    df['EMA_medium'] = ta.ema(df.Close, length=ema_medium)
    df['EMA_long'] = ta.ema(df.Close, length=ema_long)
    df['EMA_long_slope'] = df['EMA_long'].diff() / df['EMA_long']  # Slope of the long EMA

    # Volatility indicators
    df['ATR'] = ta.atr(df.High, df.Low, df.Close, length=atr_length)
    bb_result = ta.bbands(df.Close, length=bb_length, std=bb_std)  # Get all BB components
    df['BB_upper'] = bb_result[f'BBU_{bb_length}_{bb_std}']
    df['BB_middle'] = bb_result[f'BBM_{bb_length}_{bb_std}']
    df['BB_lower'] = bb_result[f'BBL_{bb_length}_{bb_std}']
    df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']

    # Momentum indicators
    df['RSI'] = ta.rsi(df.Close, length=rsi_length)

    # Trend strength (ADX)
    adx = ta.adx(df.High, df.Low, df.Close, length=adx_length)
    df['ADX'] = adx[f'ADX_{adx_length}']
    df['DI+'] = adx[f'DMP_{adx_length}']  # Positive Directional Indicator
    df['DI-'] = adx[f'DMN_{adx_length}']  # Negative Directional Indicator

    # Volume indicators - dynamic volume threshold
    df['Vol_MA'] = ta.sma(df.Volume, length=20)
    volume_multiplier = 1.2  # Look for volume 20% above average
    df['Volume_Condition'] = (df['Volume'] > (df['Vol_MA'] * volume_multiplier)) & (df['Volume'] > df['Volume'].shift())

    # Consolidation Filter - Avoid trading in choppy markets
    df['Consolidation'] = (df['BB_width'] < consolidation_threshold) & (df['ATR'] / df['Close'] < 0.01) #added ATR filter

    # --- Entry conditions ---
    # Buy (Long)
    df['Buy_Signal'] = (
        (df['EMA_short'] > df['EMA_medium']) &
        (df['EMA_medium'] > df['EMA_long']) &
        (df['EMA_long_slope'] > 0) &         # Long-term trend is up
        (df['DI+'] > df['DI-']) &             # Confirm trend with ADX
        (df['RSI'] > 50) &                   # RSI above midpoint (not necessarily oversold)
        (df['Close'] < df['BB_middle']) &   # Price near lower BB (but within uptrend)
        (df['Volume_Condition']) &         # Volume confirmation
        (~df['Consolidation'])              # Not in consolidation
        | (df['Close'] < df['BB_lower']) & (df['Volume_Condition'])  # added breakout
    )


    # Sell (Short)
    df['Sell_Signal'] = (
        (df['EMA_short'] < df['EMA_medium']) &
        (df['EMA_medium'] < df['EMA_long']) &
        (df['EMA_long_slope'] < 0) &          # Long-term trend is down
        (df['DI-'] > df['DI+']) &              # Confirm trend with ADX
        (df['RSI'] < 50) &                    # RSI below midpoint (not necessarily overbought)
        (df['Close'] > df['BB_middle']) &    # Price near upper BB (but within downtrend)
        (df['Volume_Condition']) &         # Volume confirmation
        (~df['Consolidation'])                # Not in consolidation
        | (df['Close'] > df['BB_upper']) & (df['Volume_Condition'])  # added breakout
    )


    # --- Assign Total Signal ---
    df['Total_Signal'] = 0  # Default: No signal
    df.loc[df['Buy_Signal'], 'Total_Signal'] = 2  # Buy
    df.loc[df['Sell_Signal'], 'Total_Signal'] = 1  # Sell

    # --- Ensure no conflicting signals ---
    conflicting = (df['Total_Signal'] == 2) & (df['Total_Signal'].shift(1) == 1)
    df.loc[conflicting, 'Total_Signal'] = 0

    # Map for compatibility with Backtesting.py
    df['TotalSignal'] = df['Total_Signal']

    return df