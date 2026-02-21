import pandas as pd
import pandas_ta as ta
import numpy as np

def fvg_confirmation_signals(df, parameters):
    """
    Calculates FVG confirmation signals based on the provided dataframe and parameters.
    This is a stateful calculation that iterates through the data.
    """
    # Parameters
    fvg_min_size_atr_multiplier = parameters.get('fvg_min_size_atr_multiplier', 0.5)
    fvg_candle_range_atr_multiplier = parameters.get('fvg_candle_range_atr_multiplier', 1.5)
    sl_atr_multiplier = parameters.get('sl_atr_multiplier', 1.0)
    fvg_expiry_bars = parameters.get('fvg_expiry_bars', 10)
    ema_length = 200
    atr_length = 14

    # Indicators
    df['EMA'] = ta.ema(df['Close'], length=ema_length)
    df['ATR'] = ta.atr(high=df['High'], low=df['Low'], close=df['Close'], length=atr_length)
    
    signals = [0] * len(df)
    active_fvg = None

    # Loop through dataframe to generate signals
    for i in range(20, len(df)):
        current_bar_index = i
        current_atr = df.at[df.index[i], 'ATR']
        price = df.at[df.index[i], 'Close']

        # --- FVG State Management & Entry ---
        if active_fvg:
            # 1. Check for FVG expiry
            if current_bar_index >= active_fvg['expiry']:
                active_fvg = None

            # 2. Check for FVG invalidation
            if active_fvg and active_fvg['type'] == 'bearish' and price > active_fvg['top']:
                active_fvg = None
            
            if active_fvg and active_fvg['type'] == 'bullish' and price < active_fvg['bottom']:
                active_fvg = None

            # 3. Check for Confirmation & Entry
            if active_fvg:
                if active_fvg['type'] == 'bearish':
                    if df.at[df.index[i], 'High'] > active_fvg['bottom']:
                        signals[i] = 1  # Sell Signal
                        active_fvg = None
                        continue
                elif active_fvg['type'] == 'bullish':
                    if df.at[df.index[i], 'Low'] < active_fvg['top']:
                        signals[i] = 2  # Buy Signal
                        active_fvg = None
                        continue
            
            if active_fvg:
                continue

        # --- FVG Detection ---
        if not active_fvg:
            if len(df) < 20:
                continue

            # Bearish FVG Signal
            if price < df.at[df.index[i], 'EMA']:
                if df.at[df.index[i-2], 'Low'] > df.at[df.index[i], 'High']:
                    fvg_top = df.at[df.index[i-2], 'Low']
                    fvg_bottom = df.at[df.index[i], 'High']
                    fvg_size = fvg_top - fvg_bottom
                    fvg_candle_range = df.at[df.index[i-1], 'High'] - df.at[df.index[i-1], 'Low']

                    if (fvg_size > fvg_min_size_atr_multiplier * current_atr and
                        fvg_candle_range > fvg_candle_range_atr_multiplier * current_atr):
                        
                        sl = df.at[df.index[i-1], 'High'] + sl_atr_multiplier * current_atr
                        
                        active_fvg = {
                            'type': 'bearish', 'top': fvg_top, 'bottom': fvg_bottom, 'sl': sl,
                            'expiry': current_bar_index + fvg_expiry_bars
                        }
                        continue

            # Bullish FVG Signal
            if price > df.at[df.index[i], 'EMA']:
                if df.at[df.index[i-2], 'High'] < df.at[df.index[i], 'Low']:
                    fvg_bottom = df.at[df.index[i-2], 'High']
                    fvg_top = df.at[df.index[i], 'Low']
                    fvg_size = fvg_top - fvg_bottom
                    fvg_candle_range = df.at[df.index[i-1], 'High'] - df.at[df.index[i-1], 'Low']

                    if (fvg_size > fvg_min_size_atr_multiplier * current_atr and
                        fvg_candle_range > fvg_candle_range_atr_multiplier * current_atr):

                        sl = df.at[df.index[i-1], 'Low'] - sl_atr_multiplier * current_atr
                        
                        active_fvg = {
                            'type': 'bullish', 'top': fvg_top, 'bottom': fvg_bottom, 'sl': sl,
                            'expiry': current_bar_index + fvg_expiry_bars
                        }
                        continue
    
    df['TotalSignal'] = signals
    return df
