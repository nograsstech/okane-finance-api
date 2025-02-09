from .clf_bollinger_rsi.clf_bollinger_rsi_15m import clf_bollinger_signals_15m
from .clf_bollinger_rsi.clf_bollinger_rsi import clf_bollinger_signals
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m import eurjpy_bollinger_rsi_60m
from .ema_bollinger.ema_bollinger import ema_bollinger_signals
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk import ema_bollinger_signals as ema_bollinger_signals_low_risk
from .macd_1.macd_1 import macd_1
from .grid_trading.grid_trading import grid_trading

def calculate_signals(df, df1d, strategy, parameters):
    print(strategy, parameters)
    try:
      if strategy == "ema_bollinger":
          return ema_bollinger_signals(df, parameters)
      elif strategy == "ema_bollinger_1_low_risk":
        return ema_bollinger_signals_low_risk(df, parameters)
      elif strategy == "macd_1":
        return macd_1(df, df1d, parameters)
      elif strategy == "clf_bollinger_rsi":
        return clf_bollinger_signals(df, parameters)
      elif strategy == "clf_bollinger_rsi_15m":
        return clf_bollinger_signals_15m(df, parameters)
      elif strategy == "eurjpy_bollinger_rsi_60m":
        return eurjpy_bollinger_rsi_60m(df, parameters)
      elif strategy == "grid_trading":
        return grid_trading(df, parameters)
      else:
          return None
    except Exception as e:
        print("calculate_signals : ERROR__________________")
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
  elif strategy == "clf_bollinger_rsi":
      return clf_bollinger_signals(df, parameters)
  elif strategy == "clf_bollinger_rsi_15m":
      return clf_bollinger_signals_15m(df, parameters)
  elif strategy == "eurjpy_bollinger_rsi_60m":
      return eurjpy_bollinger_rsi_60m(df, parameters)
  elif strategy == "grid_trading":
      return grid_trading(df, parameters)
  else:
      return None
    