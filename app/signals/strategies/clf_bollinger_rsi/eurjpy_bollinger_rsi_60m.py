import pandas_ta as ta

# Default parameters
atr_length=14
bb_length=30
bb_std=2
rsi_length=14
rsi_threshold_low=30
rsi_threshold_high=70
bb_width_threshold=0.0015

def eurjpy_bollinger_rsi_60m(df, parameters):
    df.ta.bbands(append=True, length=bb_length, std=bb_std)
    df.ta.rsi(append=True, length=rsi_length)
    df["atr"] = ta.atr(low = df.Low, close = df.Close, high = df.High, length=atr_length)

    # Rename columns for clarity if necessary
    df.rename(columns={
        'BBL_30_2.0': 'bbl', 'BBM_30_2.0': 'bbm', 'BBU_30_2.0': 'bbh', 'RSI_14': 'rsi'
    }, inplace=True)

    # Calculate Bollinger Bands Width
    df['bb_width'] = (df['bbh'] - df['bbl']) / df['bbm']
    
    # Initialize the 'TotalSignal' column
    df['TotalSignal'] = 0

    for i in range(1, len(df)):
        # Previous candle conditions for BUY
        prev_candle_closes_below_bb = df['Close'].iloc[i-1] < df['bbl'].iloc[i-1]
        prev_rsi_below_thr = df['rsi'].iloc[i-1] < rsi_threshold_low
        # Current candle conditions for BUY
        closes_above_prev_high = df['Close'].iloc[i] > df['High'].iloc[i-1]
        bb_width_greater_threshold = df['bb_width'].iloc[i] > bb_width_threshold

        # Combine conditions for BUY
        if (prev_candle_closes_below_bb and
            prev_rsi_below_thr and
            closes_above_prev_high and
            bb_width_greater_threshold):
            df.loc[df.index[i], 'TotalSignal'] = 2  # Set the buy signal for the current candle

        # Previous candle conditions for SELL
        prev_candle_closes_above_bb = df['Close'].iloc[i-1] > df['bbh'].iloc[i-1]
        prev_rsi_above_thr = df['rsi'].iloc[i-1] > rsi_threshold_high
        # Current candle conditions for SELL
        closes_below_prev_low = df['Close'].iloc[i] < df['Low'].iloc[i-1]
        bb_width_greater_threshold = df['bb_width'].iloc[i] > bb_width_threshold

        # Combine conditions for SELL
        if (prev_candle_closes_above_bb and
            prev_rsi_above_thr and
            closes_below_prev_low and
            bb_width_greater_threshold):
            df.loc[df.index[i], 'TotalSignal'] = 1  # Set the sell signal for the current candle
    # df.dropna(subset=['Close'], inplace=True)
    
    return df