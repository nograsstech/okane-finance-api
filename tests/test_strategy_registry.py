"""
Unit tests for strategy registry and adapters.

Tests the StrategyInterface, StrategyRegistry, and LegacySignalAdapter.
"""
from unittest.mock import Mock

import pytest

from app.signals.strategies.adapters import LegacySignalAdapter
from app.signals.strategies.base import StrategyInterface
from app.signals.strategies.registry import StrategyRegistry


class MockStrategy(StrategyInterface):
    """Mock strategy for testing."""

    def __init__(self, name):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def calculate_signals(self, df, df1d, parameters):
        return df

    def run_backtest(self, df, strategy_parameters, **kwargs):
        return (Mock(), Mock(), [], {})


class TestStrategyInterface:
    """Test suite for StrategyInterface."""

    def test_display_name_default(self):
        """Test default display name generation."""
        strategy = MockStrategy("test_strategy_name")
        assert strategy.display_name == "Test Strategy Name"

    def test_display_name_uses_underscore_replacement(self):
        """Test that underscores are replaced with spaces."""
        strategy = MockStrategy("ema_bollinger_macd")
        assert strategy.display_name == "Ema Bollinger Macd"

    def test_description_default(self):
        """Test default description is None."""
        strategy = MockStrategy("test")
        assert strategy.description is None

    def test_get_default_parameters_returns_empty_dict(self):
        """Test default parameters returns empty dict."""
        strategy = MockStrategy("test")
        assert strategy.get_default_parameters() == {}

    def test_run_backtest_raises_not_implemented(self):
        """Test that run_backtest raises NotImplementedError by default."""

        class MinimalStrategy(StrategyInterface):
            @property
            def name(self):
                return "minimal"

            def calculate_signals(self, df, df1d, parameters):
                return df

        strategy = MinimalStrategy()
        with pytest.raises(NotImplementedError):
            strategy.run_backtest(Mock(), {})


class TestStrategyRegistry:
    """Test suite for StrategyRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        StrategyRegistry.clear()

    def test_register_strategy(self):
        """Test registering a strategy."""
        strategy = MockStrategy("test_strategy")
        StrategyRegistry.register(strategy)

        assert StrategyRegistry.is_registered("test_strategy")

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate strategy raises ValueError."""
        strategy1 = MockStrategy("test_strategy")
        strategy2 = MockStrategy("test_strategy")

        StrategyRegistry.register(strategy1)

        with pytest.raises(ValueError, match="already registered"):
            StrategyRegistry.register(strategy2)

    def test_get_strategy(self):
        """Test retrieving a registered strategy."""
        strategy = MockStrategy("test_strategy")
        StrategyRegistry.register(strategy)

        retrieved = StrategyRegistry.get("test_strategy")

        assert retrieved is strategy

    def test_get_nonexistent_strategy_returns_none(self):
        """Test that getting nonexistent strategy returns None."""
        retrieved = StrategyRegistry.get("nonexistent")
        assert retrieved is None

    def test_list_all_returns_all_strategies(self):
        """Test that list_all returns all registered strategies."""
        strategy1 = MockStrategy("strategy1")
        strategy2 = MockStrategy("strategy2")

        StrategyRegistry.register(strategy1)
        StrategyRegistry.register(strategy2)

        strategies = StrategyRegistry.list_all()

        assert set(strategies) == {"strategy1", "strategy2"}

    def test_clear_removes_all_strategies(self):
        """Test that clear removes all strategies."""
        strategy = MockStrategy("test_strategy")
        StrategyRegistry.register(strategy)

        StrategyRegistry.clear()

        assert not StrategyRegistry.is_registered("test_strategy")
        assert StrategyRegistry.list_all() == []

    def test_is_registered(self):
        """Test is_registered method."""
        strategy = MockStrategy("test_strategy")

        assert not StrategyRegistry.is_registered("test_strategy")

        StrategyRegistry.register(strategy)

        assert StrategyRegistry.is_registered("test_strategy")


class TestLegacySignalAdapter:
    """Test suite for LegacySignalAdapter."""

    def test_adapter_implements_interface(self):
        """Test that adapter implements StrategyInterface."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("test", signal_func)

        assert isinstance(adapter, StrategyInterface)

    def test_name_property(self):
        """Test name property."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("test_strategy", signal_func)

        assert adapter.name == "test_strategy"

    def test_display_name_custom(self):
        """Test custom display name."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter(
            "test", signal_func, display_name="Custom Name"
        )

        assert adapter.display_name == "Custom Name"

    def test_display_name_default_from_name(self):
        """Test default display name is derived from name."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("ema_bollinger", signal_func)

        assert adapter.display_name == "Ema Bollinger"

    def test_calculate_signals_calls_signal_func(self):
        """Test that calculate_signals calls the wrapped function."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("test", signal_func)

        df = Mock()
        df1d = Mock()
        parameters = {"test": 1}

        result = adapter.calculate_signals(df, df1d, parameters)

        signal_func.assert_called_once_with(df, df1d, parameters)
        assert result == signal_func.return_value

    def test_run_backtest_calls_backtest_func(self):
        """Test that run_backtest calls the wrapped backtest function."""
        backtest_func = Mock(return_value=(Mock(), Mock(), [], {}))
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("test", signal_func, backtest_func)

        df = Mock()
        parameters = {"test": 1}

        result = adapter.run_backtest(df, parameters, size=0.05, skip_optimization=True)

        # Verify standard signature
        backtest_func.assert_called_once_with(df, parameters, 0.05, True, None)
        assert result == backtest_func.return_value

    def test_run_backtest_grid_trading_signature(self):
        """Test that grid_trading uses special signature without size."""
        backtest_func = Mock(return_value=(Mock(), Mock(), [], {}))
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("grid_trading", signal_func, backtest_func)

        df = Mock()
        parameters = {"test": 1}

        result = adapter.run_backtest(df, parameters, size=0.05)

        # Verify grid_trading signature (no size parameter)
        backtest_func.assert_called_once_with(df, parameters, False, None)
        assert result == backtest_func.return_value

    def test_run_backtest_without_backtest_func_raises_error(self):
        """Test that run_backtest raises NotImplementedError when no backtest_func."""
        signal_func = Mock(return_value=Mock())
        adapter = LegacySignalAdapter("test", signal_func, backtest_func=None)

        with pytest.raises(NotImplementedError, match="not available"):
            adapter.run_backtest(Mock(), {})
