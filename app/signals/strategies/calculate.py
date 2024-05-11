from .ema_bollinger import ema_bollinger_signals
from .ema_bollinger_1_low_risk import ema_bollinger_signals as ema_bollinger_signals_low_risk
from .macd_1 import macd_1

def calculate_signals(df, df1d, strategy, parameters):
    print(strategy, parameters)
    try:
      if strategy == "ema_bollinger":
          return ema_bollinger_signals(df, parameters)
      elif strategy == "ema_bollinger_1_low_risk":
        return ema_bollinger_signals_low_risk(df, parameters)
      elif strategy == "macd_1":
        return macd_1(df, df1d, parameters)
      else:
          return None
    except Exception as e:
        print("ERROR__________________")
        print(e)
        return None
      
      
async def calculate_signals_async(df, df1d, strategy, parameters):
  print(strategy)
  if strategy == "ema_bollinger":
    return ema_bollinger_signals(df, parameters)
  elif strategy == "ema_bollinger_1_low_risk":
        return ema_bollinger_signals_low_risk(df, parameters)
  elif strategy == "macd_1":
      return macd_1(df, df1d, parameters)
  else:
      return None
    