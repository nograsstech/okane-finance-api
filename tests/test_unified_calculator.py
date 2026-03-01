"""
Unit tests for unified_calculator module.

Tests the signal calculation dispatcher that replaced the duplicate if-elif chains.
"""

import pandas as pd
import pytest

from app.signals.strategies.unified_calculator import (
    _STRATEGY_FUNCTIONS,
    calculate_signals,
    calculate_signals_async,
    calculate_signals_unified,
)


class TestUnifiedCalculator:
    """Test suite for unified signal calculator."""

    def test_strategy_registry_contains_all_strategies(self):
        """Verify all expected strategies are in the registry."""
        expected_strategies = [
            "ema_bollinger",
            "ema_bollinger_1_low_risk",
            "macd_1",
            "clf_bollinger_rsi",
            "clf_bollinger_rsi_15m",
            "eurjpy_bollinger_rsi_60m",
            "grid_trading",
            "super_safe_strategy",
            "fvg_confirmation",
            "swing-1",
        ]
        assert set(_STRATEGY_FUNCTIONS.keys()) == set(expected_strategies)

    def test_calculate_signals_unified_with_invalid_strategy(self):
        """Test that invalid strategy returns None."""
        df = pd.DataFrame({"Close": [1, 2, 3]})
        result = calculate_signals_unified(df, None, "invalid_strategy", {})
        assert result is None

    def test_calculate_signals_unified_handles_exceptions(self):
        """Test that exceptions are caught and None is returned."""
        # Create a simple mock that raises an exception
        import app.signals.strategies.unified_calculator as calc_module
        original_registry = calc_module._STRATEGY_FUNCTIONS.copy()

        try:
            # Add a test function that raises an exception
            def failing_strategy(df, df1d, parameters):
                raise Exception("Test error")

            calc_module._STRATEGY_FUNCTIONS['test_failing'] = failing_strategy

            df = pd.DataFrame({"Close": [1, 2, 3]})
            result = calculate_signals_unified(df, None, "test_failing", {})

            assert result is None
        finally:
            # Restore original registry
            calc_module._STRATEGY_FUNCTIONS = original_registry

    def test_calculate_signals_sync_wrapper(self):
        """Test that sync wrapper delegates to unified function."""
        df = pd.DataFrame({"Close": [1, 2, 3]})

        # Test with invalid strategy to verify delegation works
        result = calculate_signals(df, None, "invalid_strategy", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_signals_async_wrapper(self):
        """Test that async wrapper delegates to unified function."""
        df = pd.DataFrame({"Close": [1, 2, 3]})

        # Test with invalid strategy to verify delegation works
        result = await calculate_signals_async(df, None, "invalid_strategy", {})
        assert result is None

    def test_all_strategy_functions_are_callable(self):
        """Test that all registered strategy functions are callable."""
        for name, func in _STRATEGY_FUNCTIONS.items():
            assert callable(func), f"Strategy '{name}' function is not callable"
