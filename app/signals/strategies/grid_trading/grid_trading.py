import numpy as np
import pandas_ta as ta

# Default parameters
atr_length=28


def grid_trading(df, parameters):
    df["atr"] = ta.atr(low = df.Low, close = df.Close, high = df.High, length=atr_length)
    


    
    return df
