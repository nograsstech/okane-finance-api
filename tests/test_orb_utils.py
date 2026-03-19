"""
Tests for ORB utilities module.

Tests timezone conversion, session detection, and OR calculations.
"""

import pytest
import importlib
from datetime import datetime, UTC

# Import from module with numeric name using importlib
orb_utils = importlib.import_module("app.signals.strategies.5_min_orb.orb_utils")

convert_utc_to_session_time = orb_utils.convert_utc_to_session_time
detect_session_window = orb_utils.detect_session_window
calculate_pip_value = orb_utils.calculate_pip_value
calculate_or_size_pips = orb_utils.calculate_or_size_pips
get_or_threshold = orb_utils.get_or_threshold
should_skip_session = orb_utils.should_skip_session


class TestConvertUtcToSessionTime:
    """Test UTC to session local time conversion with DST handling."""

    def test_convert_utc_to_london_winter(self):
        """January should be GMT+0 (no DST)."""
        # January 15, 2025, 10:00 UTC = 10:00 London time (GMT)
        utc_time = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
        london_time = convert_utc_to_session_time(utc_time, "london")

        assert london_time.hour == 10
        assert london_time.minute == 0

    def test_convert_utc_to_london_summer(self):
        """July should be GMT+1 (BST with DST)."""
        # July 15, 2025, 10:00 UTC = 11:00 London time (BST)
        utc_time = datetime(2025, 7, 15, 10, 0, tzinfo=UTC)
        london_time = convert_utc_to_session_time(utc_time, "london")

        assert london_time.hour == 11
        assert london_time.minute == 0

    def test_convert_utc_to_ny_est(self):
        """January should be EST (GMT-5, no DST)."""
        # January 15, 2025, 15:00 UTC = 10:00 NY time (EST)
        utc_time = datetime(2025, 1, 15, 15, 0, tzinfo=UTC)
        ny_time = convert_utc_to_session_time(utc_time, "ny")

        assert ny_time.hour == 10
        assert ny_time.minute == 0

    def test_convert_utc_to_ny_edt(self):
        """July should be EDT (GMT-4, with DST)."""
        # July 15, 2025, 14:00 UTC = 10:00 NY time (EDT)
        utc_time = datetime(2025, 7, 15, 14, 0, tzinfo=UTC)
        ny_time = convert_utc_to_session_time(utc_time, "ny")

        assert ny_time.hour == 10
        assert ny_time.minute == 0


class TestDetectSessionWindow:
    """Test session window detection."""

    def test_detect_session_window_london_active(self):
        """08:10 London time should be 'active' (after 08:05)."""
        # January 15, 2025, 08:10 UTC = 08:10 London time
        utc_time = datetime(2025, 1, 15, 8, 10, tzinfo=UTC)
        window = detect_session_window(utc_time, "london")

        assert window == "active"

    def test_detect_session_window_london_inactive(self):
        """12:00 London time should be None (outside active window)."""
        # January 15, 2025, 12:00 UTC = 12:00 London time
        utc_time = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)
        window = detect_session_window(utc_time, "london")

        assert window is None

    def test_detect_session_window_ny_active(self):
        """09:40 NY time should be 'active' (after 09:35)."""
        # July 15, 2025, 14:40 UTC = 10:40 NY time (EDT, GMT-4)
        # Actually 14:40 UTC = 10:40 EDT, so 09:40 EDT = 13:40 UTC
        utc_time = datetime(2025, 7, 15, 13, 40, tzinfo=UTC)
        window = detect_session_window(utc_time, "ny")

        assert window == "active"


class TestCalculatePipValue:
    """Test pip value calculation."""

    def test_calculate_pip_value_eurusd(self):
        """EUR/USD should return 0.0001."""
        assert calculate_pip_value("EUR/USD") == 0.0001
        assert calculate_pip_value("EURUSD") == 0.0001

    def test_calculate_pip_value_usdjpy(self):
        """USD/JPY should return 0.01."""
        assert calculate_pip_value("USD/JPY") == 0.01
        assert calculate_pip_value("USDJPY") == 0.01

    def test_calculate_pip_value_gbpusd(self):
        """GBP/USD should return 0.0001."""
        assert calculate_pip_value("GBP/USD") == 0.0001


class TestCalculateOrSizePips:
    """Test OR size calculation in pips."""

    def test_calculate_or_size_pips(self):
        """Simple calculation test."""
        # EUR/USD: 1.0850 - 1.0800 = 0.0050 = 50 pips
        or_high = 1.0850
        or_low = 1.0800
        pip_value = 0.0001

        size_pips = calculate_or_size_pips(or_high, or_low, pip_value)

        assert size_pips == pytest.approx(50)

    def test_calculate_or_size_pips_jpy(self):
        """USD/JPY: 150.50 - 150.00 = 0.50 = 50 pips."""
        or_high = 150.50
        or_low = 150.00
        pip_value = 0.01

        size_pips = calculate_or_size_pips(or_high, or_low, pip_value)

        assert size_pips == 50


class TestGetOrThreshold:
    """Test OR threshold retrieval."""

    def test_get_or_threshold_eurusd_london(self):
        """EUR/USD London should be 40 pips."""
        assert get_or_threshold("EUR/USD", "london") == 40
        assert get_or_threshold("EURUSD", "london") == 40

    def test_get_or_threshold_eurusd_ny(self):
        """EUR/USD NY should be 35 pips."""
        assert get_or_threshold("EUR/USD", "ny") == 35

    def test_get_or_threshold_gbpusd_london(self):
        """GBP/USD London should be 50 pips."""
        assert get_or_threshold("GBP/USD", "london") == 50

    def test_get_or_threshold_gbpusd_ny(self):
        """GBP/USD NY should be 45 pips."""
        assert get_or_threshold("GBP/USD", "ny") == 45

    def test_get_or_threshold_usdjpy_ny(self):
        """USD/JPY NY should be 40 pips."""
        assert get_or_threshold("USD/JPY", "ny") == 40

    def test_get_or_threshold_eurgbp_london(self):
        """EUR/GBP London should be 40 pips."""
        assert get_or_threshold("EUR/GBP", "london") == 40

    def test_get_or_threshold_gbpjpy_london(self):
        """GBP/JPY London should be 45 pips."""
        assert get_or_threshold("GBP/JPY", "london") == 45


class TestShouldSkipSession:
    """Test session skip logic."""

    def test_should_skip_session_too_small(self):
        """OR size below minimum should skip."""
        should_skip, reason = should_skip_session(3, "EUR/USD", "london")

        assert should_skip is True
        assert "minimum" in reason.lower()

    def test_should_skip_session_within_threshold(self):
        """OR size within threshold should not skip."""
        should_skip, reason = should_skip_session(35, "EUR/USD", "london")

        assert should_skip is False
        assert reason is None

    def test_should_skip_session_exceeds_threshold(self):
        """OR size exceeds threshold should skip."""
        should_skip, reason = should_skip_session(45, "EUR/USD", "london")

        assert should_skip is True
        assert "threshold" in reason.lower()

    def test_should_skip_session_unconfigured_ticker(self):
        """Unconfigured ticker should not skip (within reason)."""
        should_skip, reason = should_skip_session(30, "AUD/USD", "london")

        # Should only skip if below minimum
        assert should_skip is False
