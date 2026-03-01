"""
Unified signal calculation using a strategy registry pattern.

This module replaces the duplicate if-elif chains in calculate.py with a
dictionary-based dispatcher, eliminating code duplication between
calculate_signals and calculate_signals_async.
"""

import pandas as pd

from .clf_bollinger_rsi.clf_bollinger_rsi import clf_bollinger_signals

# Import all strategy signal functions
from .clf_bollinger_rsi.clf_bollinger_rsi_15m import clf_bollinger_signals_15m
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m import eurjpy_bollinger_rsi_60m
from .ema_bollinger.ema_bollinger import ema_bollinger_signals
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk import (
    ema_bollinger_signals as ema_bollinger_signals_low_risk,
)
from .forex_fvg_respected.fvg_confirmation import fvg_confirmation_signals
from .grid_trading.grid_trading import grid_trading
from .macd_1.macd_1 import macd_1
from .super_safe_strategy.super_safe_strategy import super_safe_strategy_signals
from .swing_1.swing_signals import swing_1_signals

# Strategy function registry - maps strategy names to their signal functions
_STRATEGY_FUNCTIONS = {
    "ema_bollinger": ema_bollinger_signals,
    "ema_bollinger_1_low_risk": ema_bollinger_signals_low_risk,
    "macd_1": macd_1,
    "clf_bollinger_rsi": clf_bollinger_signals,
    "clf_bollinger_rsi_15m": clf_bollinger_signals_15m,
    "eurjpy_bollinger_rsi_60m": eurjpy_bollinger_rsi_60m,
    "grid_trading": grid_trading,
    "super_safe_strategy": super_safe_strategy_signals,
    "fvg_confirmation": fvg_confirmation_signals,
    "swing-1": swing_1_signals,
}

# Strategies that require daily timeframe data (df1d parameter)
_STRATEGIES_REQUIRING_DAILY_DATA = {"macd_1"}


def calculate_signals_unified(
    df: pd.DataFrame,
    df1d: pd.DataFrame | None,
    strategy: str,
    parameters: dict
) -> pd.DataFrame | None:
    """
    Unified signal calculation using the strategy dispatcher.

    This single implementation replaces both calculate_signals and
    calculate_signals_async. The underlying strategy calculations are
    CPU-bound pandas operations, so there's no actual async behavior
    in the original implementations - both were just wrapper functions
    with identical if-elif chains.

    Args:
        df: Primary timeframe OHLCV data
        df1d: Daily timeframe data (required for some strategies like macd_1)
        strategy: Strategy name (e.g., 'ema_bollinger', 'macd_1')
        parameters: Strategy-specific parameters

    Returns:
        DataFrame with TotalSignal column added, or None if strategy not found

    Raises:
        Exception: Propagates any exception from the strategy function
    """
    print(strategy, parameters)

    func = _STRATEGY_FUNCTIONS.get(strategy)
    if func is None:
        print(f"Strategy '{strategy}' not found in registry")
        return None

    try:
        # Call with or without df1d depending on the strategy
        if strategy in _STRATEGIES_REQUIRING_DAILY_DATA:
            return func(df, df1d, parameters)
        else:
            return func(df, parameters)
    except Exception as e:
        print(f"calculate_signals_unified: ERROR for strategy '{strategy}'")
        print(e)
        return None


# Backward compatibility wrappers - maintain exact same interface as before
def calculate_signals(df, df1d, strategy, parameters):
    """
    Legacy sync wrapper for backward compatibility.

    This maintains the exact same function signature that existing code expects.
    """
    return calculate_signals_unified(df, df1d, strategy, parameters)


async def calculate_signals_async(df, df1d, strategy, parameters):
    """
    Legacy async wrapper for backward compatibility.

    Note: This doesn't make the calculation async (pandas operations are
    CPU-bound), but maintains the existing async interface that callers expect.
    The original implementation was also not truly async - it was just a
    wrapper with the same if-elif chain.
    """
    print(strategy)
    return calculate_signals_unified(df, df1d, strategy, parameters)
