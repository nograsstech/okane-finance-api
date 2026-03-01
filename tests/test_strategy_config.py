"""
Unit tests for strategy configuration management.

Tests the centralized strategy configuration system.
"""

from app.signals.strategies.config import (
    STRATEGY_CONFIGS,
    BacktestConfig,
    StrategyConfig,
    get_default_size,
    get_strategy_config,
    get_strategy_display_name,
    requires_daily_data,
)


class TestStrategyConfig:
    """Test suite for StrategyConfig dataclass."""

    def test_strategy_config_creation(self):
        """Test creating a strategy config."""
        config = StrategyConfig(
            name="test_strategy",
            display_name="Test Strategy",
            default_size=0.05,
            requires_daily_data=True,
        )

        assert config.name == "test_strategy"
        assert config.display_name == "Test Strategy"
        assert config.default_size == 0.05
        assert config.requires_daily_data is True

    def test_strategy_config_defaults(self):
        """Test default values for strategy config."""
        config = StrategyConfig(name="test", display_name="Test")

        assert config.description is None
        assert config.default_size == 0.03
        assert config.requires_daily_data is False
        assert config.default_parameters == {}


class TestBacktestConfig:
    """Test suite for BacktestConfig dataclass."""

    def test_backtest_config_defaults(self):
        """Test default backtest configuration values."""
        config = BacktestConfig()

        assert config.default_cash == 100000
        assert config.default_margin == 1/500
        assert config.max_optimization_tries == 300
        assert config.optimization_random_state == 0


class TestStrategyConfigs:
    """Test suite for the global strategy configurations."""

    def test_all_expected_strategies_have_configs(self):
        """Test that all expected strategies have configurations."""
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

        for strategy_name in expected_strategies:
            assert strategy_name in STRATEGY_CONFIGS

    def test_macd_1_requires_daily_data(self):
        """Test that macd_1 is configured to require daily data."""
        config = STRATEGY_CONFIGS.get("macd_1")
        assert config is not None
        assert config.requires_daily_data is True

    def test_other_strategies_do_not_require_daily_data(self):
        """Test that other strategies don't require daily data."""
        strategies_not_requiring_daily = [
            "ema_bollinger",
            "grid_trading",
            "swing-1",
        ]

        for strategy_name in strategies_not_requiring_daily:
            config = STRATEGY_CONFIGS.get(strategy_name)
            assert config is not None
            assert config.requires_daily_data is False


class TestGetStrategyConfig:
    """Test suite for get_strategy_config function."""

    def test_get_existing_strategy_config(self):
        """Test getting config for existing strategy."""
        config = get_strategy_config("ema_bollinger")

        assert config is not None
        assert config.name == "ema_bollinger"
        assert config.display_name == "EMA Bollinger"

    def test_get_nonexistent_strategy_config_returns_none(self):
        """Test getting config for nonexistent strategy returns None."""
        config = get_strategy_config("nonexistent_strategy")
        assert config is None


class TestGetDefaultSize:
    """Test suite for get_default_size function."""

    def test_get_default_size_for_btc_usd(self):
        """Test that BTC-USD gets special 0.01 size."""
        size = get_default_size("ema_bollinger", "BTC-USD")
        assert size == 0.01

    def test_get_default_size_from_config(self):
        """Test getting default size from strategy config."""
        size = get_default_size("ema_bollinger", "AAPL")
        assert size == 0.03

    def test_get_default_size_fallback_for_unknown_strategy(self):
        """Test fallback default size for unknown strategy."""
        size = get_default_size("unknown_strategy", "AAPL")
        assert size == 0.03

    def test_get_default_size_btc_takes_precedence(self):
        """Test that BTC-USD special handling takes precedence over config."""
        # Even if config has different size, BTC-USD should get 0.01
        size = get_default_size("ema_bollinger", "BTC-USD")
        assert size == 0.01


class TestGetStrategyDisplayName:
    """Test suite for get_strategy_display_name function."""

    def test_get_display_name_from_config(self):
        """Test getting display name from config."""
        name = get_strategy_display_name("ema_bollinger")
        assert name == "EMA Bollinger"

    def test_get_display_name_fallback(self):
        """Test fallback display name generation for unknown strategy."""
        name = get_strategy_display_name("unknown_strategy_name")
        assert name == "Unknown Strategy Name"


class TestRequiresDailyData:
    """Test suite for requires_daily_data function."""

    def test_macd_1_requires_daily_data(self):
        """Test that macd_1 requires daily data."""
        assert requires_daily_data("macd_1") is True

    def test_ema_bollinger_does_not_require_daily_data(self):
        """Test that ema_bollinger doesn't require daily data."""
        assert requires_daily_data("ema_bollinger") is False

    def test_unknown_strategy_does_not_require_daily_data(self):
        """Test that unknown strategy doesn't require daily data."""
        assert requires_daily_data("unknown_strategy") is False
