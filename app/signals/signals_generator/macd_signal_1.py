def macd_signal_1(df, backcandles):
    backcandles = 15
    # calcualte macd signal
    macd_signal = [0]*len(df)
    for row in range(1, len(df)):
        if(
            True
            and df.MACD_HIST.iloc[row-1] < 0 and df.MACD_HIST.iloc[row] > 0
        ):
            macd_signal[row]=1
        elif  (
            True
            and df.MACD_HIST.iloc[row-1] > 0 and df.MACD_HIST.iloc[row] < 0
        ):
            macd_signal[row]=-1

    df['MACDSignal'] = macd_signal
    return df