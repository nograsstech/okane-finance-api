"""
Auto-registration of all strategies.

Import this module to populate the strategy registry with all available strategies.
This module wraps existing legacy strategy functions in LegacySignalAdapter instances
and registers them with the StrategyRegistry.
"""
from app.signals.strategies.adapters import LegacySignalAdapter
from app.signals.strategies.registry import StrategyRegistry

from .clf_bollinger_rsi.clf_bollinger_rsi import clf_bollinger_signals
from .clf_bollinger_rsi.clf_bollinger_rsi_15m import clf_bollinger_signals_15m
from .clf_bollinger_rsi.clf_bollinger_rsi_backtest import backtest as clf_bollinger_rsi_backtest
from .clf_bollinger_rsi.clf_bollinger_rsi_backtest_15m import (
    backtest as clf_bollinger_rsi_backtest_15m,
)
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m import eurjpy_bollinger_rsi_60m
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m_backtest import (
    backtest as eurjpy_bollinger_rsi_60m_backtest,
)

# Import all signal functions
from .ema_bollinger.ema_bollinger import ema_bollinger_signals

# Import all backtest functions
from .ema_bollinger.ema_bollinger_backtest import backtest as ema_bollinger_backtest
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk import (
    ema_bollinger_signals as ema_bollinger_signals_low_risk,
)
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk_backtest import (
    backtest as ema_bollinger_1_low_risk_backtest,
)
from .forex_fvg_respected.fvg_confirmation import fvg_confirmation_signals
from .forex_fvg_respected.fvg_confirmation_backtest import backtest as fvg_confirmation_backtest
from .grid_trading.grid_trading import grid_trading
from .grid_trading.grid_trading_backtest import backtest as grid_trading_backtest
from .macd_1.macd_1 import macd_1
from .macd_1.macd_1_backtest import backtest as macd_1_backtest
from .super_safe_strategy.super_safe_strategy import super_safe_strategy_signals
from .super_safe_strategy.super_safe_strategy_backtest import (
    backtest as super_safe_strategy_backtest,
)
from .swing_1.swing_backtest import backtest as swing_1_backtest
from .swing_1.swing_signals import swing_1_signals


def register_all_strategies() -> None:
    """
    Register all strategies with the global registry.

    Wraps each legacy signal function in a LegacySignalAdapter and
    registers it with the StrategyRegistry. Safe to call multiple times.
    """
    strategies = [
        # (name, signal_func, backtest_func, display_name, description)
        ("ema_bollinger", ema_bollinger_signals, ema_bollinger_backtest, "EMA Bollinger", None),
        ("ema_bollinger_1_low_risk", ema_bollinger_signals_low_risk, ema_bollinger_1_low_risk_backtest, "EMA Bollinger Low Risk", None),
        ("macd_1", macd_1, macd_1_backtest, "MACD #1", None),
        ("clf_bollinger_rsi", clf_bollinger_signals, clf_bollinger_rsi_backtest, "Classifier Bollinger RSI", None),
        ("clf_bollinger_rsi_15m", clf_bollinger_signals_15m, clf_bollinger_rsi_backtest_15m, "Classifier Bollinger RSI 15m", None),
        ("eurjpy_bollinger_rsi_60m", eurjpy_bollinger_rsi_60m, eurjpy_bollinger_rsi_60m_backtest, "EUR/JPY Bollinger RSI 60m", None),
        ("grid_trading", grid_trading, grid_trading_backtest, "Grid Trading", None),
        ("super_safe_strategy", super_safe_strategy_signals, super_safe_strategy_backtest, "Super Safe Strategy", None),
        ("fvg_confirmation", fvg_confirmation_signals, fvg_confirmation_backtest, "FVG Confirmation", None),
        ("swing-1", swing_1_signals, swing_1_backtest, "Swing #1", None),
    ]

    for name, signal_func, backtest_func, display_name, description in strategies:
        # Check if already registered to avoid duplicates
        if not StrategyRegistry.is_registered(name):
            adapter = LegacySignalAdapter(
                name=name,
                signal_func=signal_func,
                backtest_func=backtest_func,
                display_name=display_name,
                description=description,
            )
            StrategyRegistry.register(adapter)
