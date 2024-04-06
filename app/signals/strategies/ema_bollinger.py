import pandas_ta as ta
from app.signals.signals_generator.rsi_signals_windowed import calculate_rsi_signal_windowed
from app.signals.signals_generator.ema_signals import ema_signal
      
def ema_bollinger_signals(df, parameters):
  # Calculate EMA and Bollinger Bands
  df["EMA_slow"]=ta.ema(df.Close, length=50)
  df["EMA_fast"]=ta.ema(df.Close, length=30)
  df['RSI']=ta.rsi(df.Close, length=10)
  my_bbands = ta.bbands(df.Close, length=15, std=1.5)
  df['ATR']=ta.atr(df.High, df.Low, df.Close, length=7)
  df=df.join(my_bbands)
  
  # Calculate EMA signals
  df = ema_signal(df,  7)
  
  # Vectorized conditions for total_signal
  condition_buy = (df['EMASignal'] == 2) & (df['Close'] <= df['BBL_15_1.5'])
  condition_sell = (df['EMASignal'] == 1) & (df['Close'] >= df['BBU_15_1.5'])

  # Assigning signals based on conditions
  df['Total_Signal'] = 0  # Default no signal
  df.loc[condition_buy, 'Total_Signal'] = 2
  df.loc[condition_sell, 'Total_Signal'] = 1
  
  # Apply the function to calculate RSI_signal
  df['RSI_signal'] = calculate_rsi_signal_windowed(df['RSI'])
  
  # Total signal
  df['TotalSignal'] = df.apply(lambda row: row['Total_Signal'] if row['Total_Signal'] == row['RSI_signal'] else 0, axis=1)
  return df
  
  