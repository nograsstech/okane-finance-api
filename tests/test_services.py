"""
Unit tests for service layer components.

Tests the extracted service modules: backtest_persistence, notification_handler, and dto_builders.
"""
from datetime import datetime
from unittest.mock import patch

from app.signals.services.dto_builders import build_backtest_stats_dto, safe_float
from app.signals.services.notification_handler import handle_trade_action_notifications


class TestSafeFloat:
    """Test suite for safe_float helper."""

    def test_safe_float_with_valid_number(self):
        """Test safe_float with a valid number."""
        assert safe_float(3.14159, decimals=2) == 3.14
        assert safe_float(10.5) == 10.5

    def test_safe_float_with_none(self):
        """Test safe_float with None returns default."""
        assert safe_float(None) == 0.0
        assert safe_float(None, default=99.0) == 99.0

    def test_safe_float_with_nan(self):
        """Test safe_float with NaN returns default."""
        assert safe_float(float('nan')) == 0.0
        assert safe_float(float('nan'), default=1.0) == 1.0

    def test_safe_float_with_infinity(self):
        """Test safe_float with infinity returns default."""
        assert safe_float(float('inf')) == 0.0
        assert safe_float(float('-inf')) == 0.0

    def test_safe_float_with_string(self):
        """Test safe_float with invalid string returns default."""
        assert safe_float("invalid") == 0.0

    def test_safe_float_with_valid_string(self):
        """Test safe_float with valid numeric string."""
        assert safe_float("123.456") == 123.456

    def test_safe_float_decimals_parameter(self):
        """Test safe_float honors decimals parameter."""
        assert safe_float(3.456789, decimals=3) == 3.457
        assert safe_float(3.456789, decimals=1) == 3.5
        assert safe_float(3.456789, decimals=0) == 3.0


class TestBuildBacktestStatsDto:
    """Test suite for build_backtest_stats_dto function."""

    def test_build_backtest_stats_dto(self):
        """Test building backtest stats DTO."""
        # Mock stats object
        stats = {
            "Max. Drawdown [%]": 10.5,
            "Start": datetime(2024, 1, 1, 12, 0, 0),
            "End": datetime(2024, 1, 31, 12, 0, 0),
            "Duration": "30 days",
            "Exposure Time [%]": 85.5,
            "Equity Final [$]": 105000,
            "Equity Peak [$]": 110000,
            "Return [%]": 5.0,
            "Buy & Hold Return [%]": 3.0,
            "Return (Ann.) [%]": 60.0,
            "Volatility (Ann.) [%]": 15.0,
            "Sharpe Ratio": 1.5,
            "Sortino Ratio": 2.0,
            "Calmar Ratio": 0.5,
            "Avg. Drawdown [%]": 5.0,
            "Max. Drawdown Duration": "10 days",
            "Avg. Drawdown Duration": "5 days",
            "# Trades": 25,
            "Win Rate [%]": 65.0,
            "Best Trade [%]": 10.0,
            "Worst Trade [%]": -5.0,
            "Avg. Trade [%]": 2.0,
            "Max. Trade Duration": "3 days",
            "Avg. Trade Duration": "1 day",
            "Profit Factor": 1.8,
        }

        dto = build_backtest_stats_dto(
            stats=stats,
            html_content="<html>test</html>",
            ticker="AAPL",
            strategy="ema_bollinger",
            period="90d",
            interval="1h",
            strategy_parameters={"tpslRatio": 2.0, "slcoef": 2.2},
        )

        # Verify all fields are present
        assert dto["ticker"] == "AAPL"
        assert dto["max_drawdown_percentage"] == 10.5
        assert dto["start_time"] == "2024-01-01 12:00:00.000000"
        assert dto["end_time"] == "2024-01-31 12:00:00.000000"
        assert dto["duration"] == "30 days"
        assert dto["final_equity"] == 105000.0
        assert dto["return_percentage"] == 5.0
        assert dto["sharpe_ratio"] == 1.5
        assert dto["win_rate"] == 65.0
        assert dto["html"] == "<html>test</html>"
        assert dto["strategy"] == "ema_bollinger"
        assert dto["period"] == "90d"
        assert dto["interval"] == "1h"
        assert dto["tpslRatio"] == 2.0
        assert dto["sl_coef"] == 2.2

    def test_build_backtest_stats_dto_handles_nan_values(self):
        """Test that NaN values are handled using safe_float."""
        stats = {
            "Max. Drawdown [%]": float('nan'),
            "Start": datetime(2024, 1, 1),
            "End": datetime(2024, 1, 31),
            "Duration": "30 days",
            "Exposure Time [%]": 85.5,
            "Equity Final [$]": 105000,
            "Equity Peak [$]": 110000,
            "Return [%]": 5.0,
            "Buy & Hold Return [%]": 3.0,
            "Return (Ann.) [%]": 60.0,
            "Volatility (Ann.) [%]": 15.0,
            "Sharpe Ratio": 1.5,
            "Sortino Ratio": 2.0,
            "Calmar Ratio": 0.5,
            "Avg. Drawdown [%]": 5.0,
            "Max. Drawdown Duration": "10 days",
            "Avg. Drawdown Duration": "5 days",
            "# Trades": 25,
            "Win Rate [%]": 65.0,
            "Best Trade [%]": 10.0,
            "Worst Trade [%]": -5.0,
            "Avg. Trade [%]": 2.0,
            "Max. Trade Duration": "3 days",
            "Avg. Trade Duration": "1 day",
            "Profit Factor": 1.8,
        }

        dto = build_backtest_stats_dto(
            stats=stats,
            html_content="",
            ticker="AAPL",
            strategy="test",
            period="90d",
            interval="1h",
            strategy_parameters={},
        )

        # NaN should be converted to default (0.0)
        assert dto["max_drawdown_percentage"] == 0.0


class TestNotificationHandler:
    """Test suite for notification handler."""

    @patch('app.signals.services.notification_handler.send_trade_action_notification')
    def test_handle_trade_action_notifications_sends_when_enabled(self, mock_send):
        """Test that notifications are sent when enabled with trade actions."""
        trade_actions = [
            {"datetime": "2024-01-01", "action": "BUY"},
            {"datetime": "2024-01-02", "action": "SELL"},
        ]

        handle_trade_action_notifications(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            notifications_on=True,
            trade_actions=trade_actions,
        )

        mock_send.assert_called_once_with(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            trade_actions=trade_actions,
        )

    @patch('app.signals.services.notification_handler.send_trade_action_notification')
    def test_handle_notifications_does_not_send_when_disabled(self, mock_send):
        """Test that notifications are not sent when disabled."""
        trade_actions = [{"action": "BUY"}]

        handle_trade_action_notifications(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            notifications_on=False,
            trade_actions=trade_actions,
        )

        mock_send.assert_not_called()

    @patch('app.signals.services.notification_handler.send_trade_action_notification')
    def test_handle_notifications_does_not_send_when_no_actions(self, mock_send):
        """Test that notifications are not sent when there are no trade actions."""
        handle_trade_action_notifications(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            notifications_on=True,
            trade_actions=[],
        )

        mock_send.assert_not_called()

    @patch('app.signals.services.notification_handler.send_trade_action_notification')
    def test_handle_notifications_handles_value_error(self, mock_send):
        """Test that ValueError (config error) is handled gracefully."""
        mock_send.side_effect = ValueError("Configuration error")

        # Should not raise exception, just log error
        handle_trade_action_notifications(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            notifications_on=True,
            trade_actions=[{"action": "BUY"}],
        )

        mock_send.assert_called_once()

    @patch('app.signals.services.notification_handler.send_trade_action_notification')
    def test_handle_notifications_handles_generic_exception(self, mock_send):
        """Test that generic exceptions are handled gracefully."""
        mock_send.side_effect = Exception("Network error")

        # Should not raise exception, just log error
        handle_trade_action_notifications(
            strategy="ema_bollinger",
            ticker="AAPL",
            interval="1h",
            notifications_on=True,
            trade_actions=[{"action": "BUY"}],
        )

        mock_send.assert_called_once()
