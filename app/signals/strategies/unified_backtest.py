"""
Unified backtest execution using a strategy registry pattern.

This module replaces the duplicate if-elif chains in perform_backtest.py with a
dictionary-based dispatcher, eliminating code duplication between
perform_backtest and perform_backtest_async.
"""

from fastapi import HTTPException

from .clf_bollinger_rsi.clf_bollinger_rsi_backtest import backtest as clf_bollinger_rsi_backtest
from .clf_bollinger_rsi.clf_bollinger_rsi_backtest_15m import (
    backtest as clf_bollinger_rsi_backtest_15m,
)
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m_backtest import (
    backtest as eurjpy_bollinger_rsi_60m_backtest,
)

# Import all backtest functions
from .ema_bollinger.ema_bollinger_backtest import backtest as ema_bollinger_backtest
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk_backtest import (
    backtest as ema_bollinger_1_low_risk_backtest,
)
from .forex_fvg_respected.fvg_confirmation_backtest import backtest as fvg_confirmation_backtest
from .grid_trading.grid_trading_backtest import backtest as grid_trading_backtest
from .macd_1.macd_1_backtest import backtest as macd_1_backtest
from .super_safe_strategy.super_safe_strategy_backtest import (
    backtest as super_safe_strategy_backtest,
)
from .swing_1.swing_backtest import backtest as swing_1_backtest


def _get_backtest_func(strategy: str):
    """
    Get the backtest function and its signature requirements for a given strategy.

    Returns a tuple of (backtest_function, signature_type) where:
    - signature_type 0: (df, parameters, size, skip_optimization, best_params)
    - signature_type 1: (df, parameters, skip_optimization, best_params) - no size param
    """
    backtest_funcs = {
        "ema_bollinger": (ema_bollinger_backtest, 0),
        "ema_bollinger_1_low_risk": (ema_bollinger_1_low_risk_backtest, 0),
        "macd_1": (macd_1_backtest, 0),
        "clf_bollinger_rsi": (clf_bollinger_rsi_backtest, 0),
        "clf_bollinger_rsi_15m": (clf_bollinger_rsi_backtest_15m, 0),
        "eurjpy_bollinger_rsi_60m": (eurjpy_bollinger_rsi_60m_backtest, 0),
        "grid_trading": (grid_trading_backtest, 1),
        "super_safe_strategy": (super_safe_strategy_backtest, 0),
        "fvg_confirmation": (fvg_confirmation_backtest, 0),
        "swing-1": (swing_1_backtest, 0),
    }

    return backtest_funcs.get(strategy)


def perform_backtest_unified(
    df,
    strategy: str,
    parameters: dict,
    skip_optimization: bool = False,
    best_params: dict | None = None,
    size: float | None = None
) -> tuple:
    """
    Unified backtest execution using the strategy dispatcher.

    This single implementation replaces both perform_backtest and
    perform_backtest_async. The backtest operations are CPU-bound,
    so there's no actual async behavior in the original implementations.

    Args:
        df: DataFrame with OHLCV data and calculated signals
        strategy: Strategy name (e.g., 'ema_bollinger', 'macd_1')
        parameters: Strategy parameters including 'size' if not provided separately
        skip_optimization: Whether to skip parameter optimization
        best_params: Pre-optimized parameters to use
        size: Position size (defaults vary by strategy)

    Returns:
        Tuple of (backtest_object, stats, trade_actions, strategy_parameters)

    Raises:
        HTTPException: If strategy not found (404)
    """
    print(strategy)

    result = _get_backtest_func(strategy)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy}' not found")

    backtest_func, sig_type = result

    try:
        # Determine size parameter
        if size is None:
            size = parameters.get('size', 0.03)

        # Call based on signature type
        if sig_type == 0:
            # Standard signature: (df, parameters, size, skip_optimization, best_params)
            return backtest_func(df, parameters, size, skip_optimization, best_params)
        else:
            # Grid trading signature: (df, parameters, skip_optimization, best_params)
            return backtest_func(df, parameters, skip_optimization, best_params)

    except HTTPException:
        raise
    except Exception as e:
        print(f"perform_backtest_unified: ERROR for strategy '{strategy}'")
        print(e)
        # Return empty values to avoid unpacking errors in the caller
        return None, None, [], {}


# Backward compatibility wrappers - maintain exact same interface as before
def perform_backtest(df, strategy, parameters, skip_optimization=False, best_params=None):
    """
    Legacy sync wrapper for backward compatibility.

    Maintains the exact same function signature that existing code expects.
    Handles size parameter extraction from parameters dict.
    """
    size = parameters.get('size', 0.03)
    return perform_backtest_unified(
        df, strategy, parameters, skip_optimization, best_params, size
    )


async def perform_backtest_async(df, strategy, parameters):
    """
    Legacy async wrapper for backward compatibility.

    Maintains the exact same function signature that existing code expects.
    The actual backtest runs in a thread pool via asyncio.to_thread() in the
    service layer, so this async wrapper is just for interface consistency.
    """
    # Handle signature variations
    if strategy == "grid_trading":
        # grid_trading doesn't take size parameter
        return perform_backtest_unified(df, strategy, parameters)
    else:
        size = parameters.get('size', 0.03)
        return perform_backtest_unified(df, strategy, parameters, False, None, size)
