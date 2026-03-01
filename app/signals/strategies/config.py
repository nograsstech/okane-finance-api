"""
Strategy configuration management.

Provides centralized configuration for all strategies, eliminating
hard-coded values and magic numbers scattered throughout the codebase.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyConfig:
    """
    Configuration for a single strategy.

    Attributes:
        name: Unique strategy identifier
        display_name: Human-readable name for UI display
        description: Optional strategy description
        default_size: Default position size for backtesting
        requires_daily_data: Whether this strategy needs daily timeframe data
        default_parameters: Default parameter values for the strategy
    """
    name: str
    display_name: str
    description: str | None = None
    default_size: float = 0.03
    requires_daily_data: bool = False
    default_parameters: dict[str, Any] = field(default_factory=dict)


# Global backtest configuration
@dataclass
class BacktestConfig:
    """Global backtest configuration defaults."""
    default_cash: int = 100000
    default_margin: float = 1/500
    max_optimization_tries: int = 300
    optimization_random_state: int = 0


# Strategy-specific configurations
STRATEGY_CONFIGS: dict[str, StrategyConfig] = {
    "ema_bollinger": StrategyConfig(
        name="ema_bollinger",
        display_name="EMA Bollinger",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "ema_bollinger_1_low_risk": StrategyConfig(
        name="ema_bollinger_1_low_risk",
        display_name="EMA Bollinger Low Risk",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "macd_1": StrategyConfig(
        name="macd_1",
        display_name="MACD #1",
        default_size=0.03,
        requires_daily_data=True,  # Requires daily data for MACD calculation
    ),
    "clf_bollinger_rsi": StrategyConfig(
        name="clf_bollinger_rsi",
        display_name="Classifier Bollinger RSI",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "clf_bollinger_rsi_15m": StrategyConfig(
        name="clf_bollinger_rsi_15m",
        display_name="Classifier Bollinger RSI 15m",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "eurjpy_bollinger_rsi_60m": StrategyConfig(
        name="eurjpy_bollinger_rsi_60m",
        display_name="EUR/JPY Bollinger RSI 60m",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "grid_trading": StrategyConfig(
        name="grid_trading",
        display_name="Grid Trading",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "super_safe_strategy": StrategyConfig(
        name="super_safe_strategy",
        display_name="Super Safe Strategy",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "fvg_confirmation": StrategyConfig(
        name="fvg_confirmation",
        display_name="FVG Confirmation",
        default_size=0.03,
        requires_daily_data=False,
    ),
    "swing-1": StrategyConfig(
        name="swing-1",
        display_name="Swing #1",
        default_size=0.03,
        requires_daily_data=False,
    ),
}


def get_strategy_config(strategy_name: str) -> StrategyConfig | None:
    """
    Get configuration for a strategy.

    Args:
        strategy_name: The strategy identifier

    Returns:
        StrategyConfig if found, None otherwise
    """
    return STRATEGY_CONFIGS.get(strategy_name)


def get_default_size(strategy_name: str, ticker: str = None) -> float:
    """
    Get default position size for a strategy.

    Args:
        strategy_name: The strategy identifier
        ticker: Optional ticker symbol (BTC-USD gets special handling)

    Returns:
        Default position size
    """
    # Special case for BTC-USD
    if ticker == "BTC-USD":
        return 0.01

    # Get from strategy config
    config = get_strategy_config(strategy_name)
    if config:
        return config.default_size

    # Fallback default
    return 0.03


def get_strategy_display_name(strategy_name: str) -> str:
    """
    Get display name for a strategy.

    Args:
        strategy_name: The strategy identifier

    Returns:
        Display name, or the strategy_name if not found
    """
    config = get_strategy_config(strategy_name)
    if config:
        return config.display_name
    return strategy_name.replace("_", " ").title()


def requires_daily_data(strategy_name: str) -> bool:
    """
    Check if a strategy requires daily timeframe data.

    Args:
        strategy_name: The strategy identifier

    Returns:
        True if daily data is required, False otherwise
    """
    config = get_strategy_config(strategy_name)
    if config:
        return config.requires_daily_data
    return False
