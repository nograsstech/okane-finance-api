"""
Unit tests for unified_backtest module.

Tests the backtest execution dispatcher that replaced the duplicate if-elif chains.
"""
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.signals.strategies.unified_backtest import (
    _get_backtest_func,
    perform_backtest,
    perform_backtest_async,
    perform_backtest_unified,
)


class TestUnifiedBacktest:
    """Test suite for unified backtest executor."""

    def test_get_backtest_func_returns_correct_function(self):
        """Test that _get_backtest_func returns the correct function for each strategy."""
        # Test standard strategies (signature type 0)
        result = _get_backtest_func("ema_bollinger")
        assert result is not None
        assert result[1] == 0  # Standard signature

        # Test grid_trading (signature type 1 - no size param)
        result = _get_backtest_func("grid_trading")
        assert result is not None
        assert result[1] == 1  # Special signature

        # Test invalid strategy
        result = _get_backtest_func("invalid_strategy")
        assert result is None

    def test_perform_backtest_unified_with_invalid_strategy(self):
        """Test that invalid strategy raises HTTPException."""
        df = Mock()

        with pytest.raises(HTTPException) as exc_info:
            perform_backtest_unified(df, "invalid_strategy", {})

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    @patch('app.signals.strategies.unified_backtest.ema_bollinger_backtest')
    def test_perform_backtest_unified_calls_standard_backtest(self, mock_backtest):
        """Test that standard backtest is called with correct parameters."""
        df = Mock()
        parameters = {"size": 0.05}
        mock_result = (Mock(), Mock(), [], {})
        mock_backtest.return_value = mock_result

        result = perform_backtest_unified(
            df, "ema_bollinger", parameters, skip_optimization=True, best_params={"test": 1}
        )

        # Verify the backtest was called with the correct signature
        mock_backtest.assert_called_once_with(df, parameters, 0.05, True, {"test": 1})
        assert result == mock_result

    @patch('app.signals.strategies.unified_backtest.grid_trading_backtest')
    def test_perform_backtest_unified_calls_grid_trading_backtest(self, mock_backtest):
        """Test that grid_trading backtest is called with special signature (no size)."""
        df = Mock()
        parameters = {"size": 0.05}
        mock_result = (Mock(), Mock(), [], {})
        mock_backtest.return_value = mock_result

        result = perform_backtest_unified(df, "grid_trading", parameters)

        # Verify grid_trading backtest was called without size parameter
        mock_backtest.assert_called_once_with(df, parameters, False, None)
        assert result == mock_result

    @patch('app.signals.strategies.unified_backtest.ema_bollinger_backtest')
    def test_perform_backtest_unified_uses_size_from_parameters(self, mock_backtest):
        """Test that size is extracted from parameters if not provided."""
        df = Mock()
        parameters = {"size": 0.07}
        mock_result = (Mock(), Mock(), [], {})
        mock_backtest.return_value = mock_result

        perform_backtest_unified(df, "ema_bollinger", parameters)

        # Verify size was extracted from parameters
        mock_backtest.assert_called_once()
        args = mock_backtest.call_args[0]
        assert args[2] == 0.07  # Third argument is size

    @patch('app.signals.strategies.unified_backtest.ema_bollinger_backtest')
    def test_perform_backtest_unified_defaults_size(self, mock_backtest):
        """Test that size defaults to 0.03 if not in parameters."""
        df = Mock()
        parameters = {}
        mock_result = (Mock(), Mock(), [], {})
        mock_backtest.return_value = mock_result

        perform_backtest_unified(df, "ema_bollinger", parameters)

        # Verify default size was used
        mock_backtest.assert_called_once()
        args = mock_backtest.call_args[0]
        assert args[2] == 0.03  # Default size

    @patch('app.signals.strategies.unified_backtest.ema_bollinger_backtest')
    def test_perform_backtest_unified_handles_exceptions(self, mock_backtest):
        """Test that exceptions are caught and empty values returned."""
        mock_backtest.side_effect = Exception("Test error")
        df = Mock()

        result = perform_backtest_unified(df, "ema_bollinger", {})

        # Should return empty values to avoid unpacking errors
        assert result == (None, None, [], {})

    @patch('app.signals.strategies.unified_backtest.perform_backtest_unified')
    def test_perform_backtest_sync_wrapper(self, mock_unified):
        """Test that sync wrapper delegates to unified function."""
        df = Mock()
        parameters = {"size": 0.05}
        mock_result = (Mock(), Mock(), [], {})
        mock_unified.return_value = mock_result

        result = perform_backtest(df, "ema_bollinger", parameters, True, {"test": 1})

        mock_unified.assert_called_once_with(df, "ema_bollinger", parameters, True, {"test": 1}, 0.05)
        assert result == mock_result

    @pytest.mark.asyncio
    @patch('app.signals.strategies.unified_backtest.perform_backtest_unified')
    async def test_perform_backtest_async_wrapper_standard(self, mock_unified):
        """Test that async wrapper delegates correctly for standard strategies."""
        df = Mock()
        parameters = {"size": 0.05}
        mock_result = (Mock(), Mock(), [], {})
        mock_unified.return_value = mock_result

        result = await perform_backtest_async(df, "ema_bollinger", parameters)

        mock_unified.assert_called_once()
        assert result == mock_result

    @pytest.mark.asyncio
    @patch('app.signals.strategies.unified_backtest.perform_backtest_unified')
    async def test_perform_backtest_async_wrapper_grid_trading(self, mock_unified):
        """Test that async wrapper handles grid_trading correctly (no size param)."""
        df = Mock()
        parameters = {"size": 0.05}
        mock_result = (Mock(), Mock(), [], {})
        mock_unified.return_value = mock_result

        result = await perform_backtest_async(df, "grid_trading", parameters)

        # grid_trading should call unified without explicit size
        mock_unified.assert_called_once_with(df, "grid_trading", parameters)
        assert result == mock_result
