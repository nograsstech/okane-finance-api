"""
Adapters to wrap legacy strategy functions into the new interface.

Provides backward compatibility by wrapping existing strategy functions
that don't implement StrategyInterface directly.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd

from app.signals.strategies.base import StrategyInterface


class LegacySignalAdapter(StrategyInterface):
    """
    Adapts legacy signal functions to the StrategyInterface.

    Allows existing strategy functions (which are standalone functions,
    not classes) to work with the new strategy registry system.
    """

    def __init__(
        self,
        name: str,
        signal_func: Callable,
        backtest_func: Callable | None = None,
        display_name: str | None = None,
        description: str | None = None,
    ):
        """
        Initialize the adapter.

        Args:
            name: Unique strategy identifier
            signal_func: Function that calculates signals
                         Signature: (df, df1d, parameters) -> DataFrame
            backtest_func: Optional function that runs backtests
                           Signature varies by strategy
            display_name: Optional human-readable name
            description: Optional strategy description
        """
        self._name = name
        self._signal_func = signal_func
        self._backtest_func = backtest_func
        self._display_name = display_name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        if self._display_name:
            return self._display_name
        return super().display_name

    @property
    def description(self) -> str | None:
        return self._description

    def calculate_signals(
        self, df: pd.DataFrame, df1d: pd.DataFrame | None, parameters: dict[str, Any]
    ) -> pd.DataFrame:
        """
        Calculate signals using the wrapped signal function.

        Args:
            df: Primary timeframe OHLCV data
            df1d: Daily timeframe data
            parameters: Strategy-specific parameters

        Returns:
            DataFrame with TotalSignal column added
        """
        return self._signal_func(df, df1d, parameters)

    def run_backtest(
        self,
        df: pd.DataFrame,
        strategy_parameters: dict[str, Any],
        size: float = 0.03,
        skip_optimization: bool = False,
        best_params: dict[str, Any] | None = None,
    ) -> tuple:
        """
        Run backtest using the wrapped backtest function.

        Handles the varying signature patterns of different strategy backtests.

        Args:
            df: DataFrame with OHLCV data and calculated signals
            strategy_parameters: Strategy parameters
            size: Position size
            skip_optimization: Whether to skip optimization
            best_params: Pre-optimized parameters

        Returns:
            Tuple of (backtest_object, stats, trade_actions, strategy_parameters)

        Raises:
            NotImplementedError: If no backtest function was provided
        """
        if self._backtest_func is None:
            raise NotImplementedError(f"Backtest not available for {self.name}")

        # Handle signature variations
        # grid_trading has a different signature (no size parameter)
        if self._name == "grid_trading":
            return self._backtest_func(df, strategy_parameters, skip_optimization, best_params)
        else:
            return self._backtest_func(
                df, strategy_parameters, size, skip_optimization, best_params
            )
