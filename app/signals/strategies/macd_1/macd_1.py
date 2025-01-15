import pandas_ta as ta
import pandas as pd
import numpy as np
from app.signals.signals_generator.macd_signal_1 import macd_signal_1

def macd_1(df, df1d, parameters):
  # MACD
  df["MACD"]=ta.macd(df.Close)['MACD_12_26_9']
  df["MACD_HIST"]=ta.macd(df.Close)['MACDh_12_26_9']
  df["MACD_SIGNAL"]=ta.macd(df.Close)['MACDs_12_26_9']
  df['RSI']=ta.rsi(df.Close, length=16)
  # MA
  df['200_MA'] = ta.sma(df.Close, length=200)
  # EMA
  df["EMA_slow"]=ta.ema(df.Close, length=50)
  df["EMA_fast"]=ta.ema(df.Close, length=30)
  # ATR
  df["ATR"] = ta.atr(low = df.Low, close = df.Close, high = df.High, length=24)
  
  # create the column called Date. its value is the index without the time
  df['Date'] = df.index.date
  df1d['Date'] = df1d.index.date
  
  # Ensure 'Date' in df and index in df1d are in the same datetime format
  df['Date'] = pd.to_datetime(df['Date'])
  df1d.index = pd.to_datetime(df1d.index)
  

  # Use a try/except block to handle missing dates
  def get_macd(row):
      try:
          return df1d.loc[row['Date']]['MACD']
      except KeyError:
          return np.nan
      
      
  def get_macd_hist(row):
      try:
          return df1d.loc[row['Date']]['MACD_HIST']
      except KeyError:
          return np.nan
      
  def get_macd_signal(row):
      try:
          return df1d.loc[row['Date']]['MACD_SIGNAL']
      except KeyError:
          return np.nan
      
  def get_adx(row):
      try:
          return df1d.loc[row['Date']]['ADX']
      except KeyError:
          return np.nan
      

  df['MACD_1d'] = df.apply(get_macd, axis=1)
  df['MACD_HIST_1d'] = df.apply(get_macd_hist, axis=1)
  df['MACD_SIGNAL_1d'] = df.apply(get_macd_signal, axis=1)
  df['ADX_1d'] = df.apply(get_adx, axis=1)
  
  # Calculate MACD signls
  df = macd_signal_1(df, 15)
  
  # Calculate RSI signals
  # Currently doesnt' work well. For future optimization
  
  # Calculate MA signals
  # Currently doesnt' work well. For future optimization
  
  # Assign Total signals
  def TotalSignal(df, l):
    if (
        df.MACDSignal[l]==1
        # and df.RSI_Signal[l]==1
        # and df.MASignal[l]==1
    ):
            return 2
    if (
        df.MACDSignal[l]==-1
        # and df.RSI_Signal[l]==-1
        # and df.MASignal[l]==-1
    ):
            return 1
    return 0
      
  def assignTotalSignal(df):
    backcandles= 14
    TotSignal = [0]*len(df)
    for row in range(backcandles, len(df)): #careful backcandles used previous cell
        TotSignal[row] = TotalSignal(df, row)
    df['TotalSignal'] = TotSignal
    return df
  
  df = assignTotalSignal(df)
  
  return df