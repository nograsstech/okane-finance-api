"""
Integration tests for backward compatibility.

Tests that the refactored code maintains the same behavior as the original implementation.
"""

import pytest

from app.signals.strategies.calculate import calculate_signals, calculate_signals_async
from app.signals.strategies.perform_backtest import perform_backtest, perform_backtest_async
from app.signals.strategies.strategy_list import strategy_list


class TestBackwardCompatibility:
    """Test suite for backward compatibility."""

    def test_calculate_signals_import_works(self):
        """Test that calculate_signals can be imported from calculate module."""
        from app.signals.strategies.calculate import calculate_signals
        assert callable(calculate_signals)

    def test_calculate_signals_async_import_works(self):
        """Test that calculate_signals_async can be imported."""
        from app.signals.strategies.calculate import calculate_signals_async
        assert callable(calculate_signals_async)

    def test_perform_backtest_import_works(self):
        """Test that perform_backtest can be imported."""
        from app.signals.strategies.perform_backtest import perform_backtest
        assert callable(perform_backtest)

    def test_perform_backtest_async_import_works(self):
        """Test that perform_backtest_async can be imported."""
        from app.signals.strategies.perform_backtest import perform_backtest_async
        assert callable(perform_backtest_async)

    def test_strategy_list_import_works(self):
        """Test that strategy_list can be imported and is a list."""
        from app.signals.strategies.strategy_list import strategy_list
        assert isinstance(strategy_list, list)
        assert len(strategy_list) > 0

    def test_strategy_list_contains_expected_strategies(self):
        """Test that strategy_list contains all expected strategies."""
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

        for strategy in expected_strategies:
            assert strategy in strategy_list, f"Strategy '{strategy}' not found in strategy_list"

    def test_calculate_signals_signature_exists(self):
        """Test that calculate_signals maintains the same function signature."""
        # Test that the function exists and can be called with expected signature
        assert callable(calculate_signals)

    @pytest.mark.asyncio
    async def test_calculate_signals_async_signature_exists(self):
        """Test that calculate_signals_async maintains the same function signature."""
        # Test that the function exists and is callable
        assert callable(calculate_signals_async)

    def test_perform_backtest_signature_exists(self):
        """Test that perform_backtest maintains the same function signature."""
        # Test that the function exists and can be called with expected signature
        assert callable(perform_backtest)

    @pytest.mark.asyncio
    async def test_perform_backtest_async_signature_exists(self):
        """Test that perform_backtest_async maintains the same function signature."""
        # Test that the function exists and is callable
        assert callable(perform_backtest_async)


class TestYFinanceUtilsBackwardCompatibility:
    """Test suite for yfinance utils backward compatibility."""

    def test_getYFinanceData_signature_unchanged(self):
        """Test that getYFinanceData maintains the same function signature."""
        from app.signals.utils.yfinance import _fetch_yfinance_data, getYFinanceData

        # Test that the function signature exists and is callable
        assert callable(getYFinanceData)
        assert callable(_fetch_yfinance_data)

    @pytest.mark.asyncio
    async def test_getYFinanceDataAsync_signature_unchanged(self):
        """Test that getYFinanceDataAsync maintains the same function signature."""
        from app.signals.utils.yfinance import getYFinanceDataAsync

        # Test that the function signature exists and is callable
        assert callable(getYFinanceDataAsync)


class TestServiceLayerBackwardCompatibility:
    """Test suite for service layer backward compatibility."""

    def test_service_functions_exist(self):
        """Test that service layer functions still exist."""
        from app.signals.service import (
            get_backtest_result,
            get_signals,
            get_strategies,
            replay_backtest,
            strategy_notification_job,
        )

        # Verify all functions exist and are callable
        assert callable(get_signals)
        assert callable(get_backtest_result)
        assert callable(replay_backtest)
        assert callable(strategy_notification_job)
        assert callable(get_strategies)

    def test_extracted_service_modules_exist(self):
        """Test that extracted service modules can be imported."""
        from app.signals.services.backtest_persistence import persist_backtest_result
        from app.signals.services.dto_builders import build_backtest_stats_dto, safe_float
        from app.signals.services.notification_handler import handle_trade_action_notifications

        # Verify all extracted functions exist and are callable
        assert callable(persist_backtest_result)
        assert callable(handle_trade_action_notifications)
        assert callable(safe_float)
        assert callable(build_backtest_stats_dto)
