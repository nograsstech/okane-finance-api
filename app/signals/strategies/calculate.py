import logging

from .clf_bollinger_rsi.clf_bollinger_rsi_15m import clf_bollinger_signals_15m
from .clf_bollinger_rsi.clf_bollinger_rsi import clf_bollinger_signals
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m import eurjpy_bollinger_rsi_60m
from .ema_bollinger.ema_bollinger import ema_bollinger_signals
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk import ema_bollinger_signals as ema_bollinger_signals_low_risk
from .macd_1.macd_1 import macd_1
from .grid_trading.grid_trading import grid_trading
from .super_safe_strategy.super_safe_strategy import super_safe_strategy_signals
from .forex_fvg_respected.fvg_confirmation import fvg_confirmation_signals
from .swing_1.swing_signals import swing_1_signals
from .double_candle.double_candle_signals import double_candle_signals
from .mean_reversion_trend_filter.mean_reversion_trend_filter_signals import mean_reversion_trend_filter_signals

# Import ORB signal functions using importlib (package names start with numbers)
import importlib
_five_min_orb_signals = importlib.import_module("app.signals.strategies.5_min_orb.five_min_orb_signals")
five_min_orb_signals = _five_min_orb_signals.five_min_orb_signals
_five_min_orb_confirmation_signals = importlib.import_module("app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_signals")
five_min_orb_confirmation_signals = _five_min_orb_confirmation_signals.five_min_orb_confirmation_signals

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
      elif strategy == "super_safe_strategy":
        return super_safe_strategy_signals(df, parameters)
      elif strategy == "fvg_confirmation":
        return fvg_confirmation_signals(df, parameters)
      elif strategy == "swing-1":
        return swing_1_signals(df, parameters)
      elif strategy == "double_candle":
        return double_candle_signals(df, parameters)
      elif strategy == "mean_reversion_trend_filter":
        # Pass both 1H and 4H data for dual-timeframe strategy
        # Handle None parameters (when calling /signals/ without parameters)
        params = parameters or {}
        df_4h = params.get('df_4h', df1d)
        return mean_reversion_trend_filter_signals(df, df_4h, params)
      elif strategy == "5_min_orb":
          return five_min_orb_signals(df, parameters)
      elif strategy == "5_min_orb_confirmation":
          return five_min_orb_confirmation_signals(df, parameters)
      else:
          return None
    except Exception as e:
        logging.error("calculate_signals failed for strategy=%s: %s", strategy, e, exc_info=True)
        raise
      
      
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
  elif strategy == "super_safe_strategy":
      return super_safe_strategy_signals(df, parameters)
  elif strategy == "fvg_confirmation":
      return fvg_confirmation_signals(df, parameters)
  elif strategy == "swing-1":
      return swing_1_signals(df, parameters)
  elif strategy == "double_candle":
      return double_candle_signals(df, parameters)
  elif strategy == "mean_reversion_trend_filter":
      # Pass both 1H and 4H data for dual-timeframe strategy
      # Handle None parameters (when calling /signals/ without parameters)
      params = parameters or {}
      df_4h = params.get('df_4h', df1d)
      return mean_reversion_trend_filter_signals(df, df_4h, params)
  elif strategy == "5_min_orb":
      return five_min_orb_signals(df, parameters)
  elif strategy == "5_min_orb_confirmation":
      return five_min_orb_confirmation_signals(df, parameters)
  else:
      return None
