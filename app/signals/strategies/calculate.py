from .ema_bollinger import ema_bollinger_signals

def calculate_signals(df, strategy, parameters):
    print(strategy)
    if strategy == "ema_bollinger":
      return ema_bollinger_signals(df, parameters)
    else:
        return None
      
      
async def calculate_signals_async(df, strategy, parameters):
  print(strategy)
  if strategy == "ema_bollinger":
    return ema_bollinger_signals(df, parameters)
  else:
      return None
    