"""
Base classes for trading strategies.

Defines the contract that all strategies must implement, providing a
standardized interface for signal calculation and backtesting.
"""
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class StrategyInterface(ABC):
    """
    Abstract base class defining the strategy contract.

    All trading strategies must implement this interface to ensure
    consistent behavior across the system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique strategy identifier.

        This should match the key used in the strategy registry and
        the value passed from the API (e.g., 'ema_bollinger', 'macd_1').
        """
        pass

    @property
    def display_name(self) -> str:
        """
        Human-readable name for UI display.

        Defaults to converting the name to title case and replacing
        underscores with spaces.
        """
        return self.name.replace("_", " ").title()

    @property
    def description(self) -> str | None:
        """
        Optional strategy description.

        Can be used to provide more context about the strategy in the UI.
        """
        return None

    @abstractmethod
    def calculate_signals(
        self,
        df: pd.DataFrame,
        df1d: pd.DataFrame | None,
        parameters: dict[str, Any]
    ) -> pd.DataFrame:
        """
        Calculate trading signals.

        Args:
            df: Primary timeframe OHLCV data
            df1d: Daily timeframe data (None if not needed by the strategy)
            parameters: Strategy-specific parameters

        Returns:
            DataFrame with TotalSignal column added (or modified in place)

        Raises:
            Exception: If signal calculation fails
        """
        pass

    def run_backtest(
        self,
        df: pd.DataFrame,
        strategy_parameters: dict[str, Any],
        size: float = 0.03,
        skip_optimization: bool = False,
        best_params: dict[str, Any] | None = None
    ) -> tuple:
        """
        Run backtest using this strategy.

        Args:
            df: DataFrame with OHLCV data and calculated signals
            strategy_parameters: Strategy parameters
            size: Position size (default varies by strategy)
            skip_optimization: Whether to skip parameter optimization
            best_params: Pre-optimized parameters to use

        Returns:
            Tuple of (backtest_object, stats, trade_actions, strategy_parameters)

        Raises:
            NotImplementedError: If backtest is not implemented for this strategy
        """
        raise NotImplementedError(f"Backtest not implemented for {self.name}")

    def get_default_parameters(self) -> dict[str, Any]:
        """
        Return default parameters for this strategy.

        Can be overridden to provide strategy-specific defaults.

        Returns:
            Dictionary of default parameter values
        """
        return {}
