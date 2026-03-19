"""
5-minute Opening Range Breakout strategies module - Version B.

Contains Version B implementation with retest confirmation.
"""
import importlib

# Import orb_utils from 5_min_orb module using importlib
# (needed because package name starts with a number)
_orb_utils = importlib.import_module("app.signals.strategies.5_min_orb.orb_utils")

convert_utc_to_session_time = _orb_utils.convert_utc_to_session_time
detect_session_window = _orb_utils.detect_session_window
calculate_pip_value = _orb_utils.calculate_pip_value
calculate_or_size_pips = _orb_utils.calculate_or_size_pips
get_or_threshold = _orb_utils.get_or_threshold
should_skip_session = _orb_utils.should_skip_session
identify_opening_range = _orb_utils.identify_opening_range

# Import signals module
_five_min_orb_confirmation_signals = importlib.import_module("app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_signals")
five_min_orb_confirmation_signals = _five_min_orb_confirmation_signals.five_min_orb_confirmation_signals

# Import backtest module
_five_min_orb_confirmation_backtest = importlib.import_module("app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_backtest")
backtest = _five_min_orb_confirmation_backtest.backtest
FiveMinORBConfirmationStrat = _five_min_orb_confirmation_backtest.FiveMinORBConfirmationStrat

__all__ = [
    "convert_utc_to_session_time",
    "detect_session_window",
    "calculate_pip_value",
    "calculate_or_size_pips",
    "get_or_threshold",
    "should_skip_session",
    "identify_opening_range",
    "five_min_orb_confirmation_signals",
    "backtest",
    "FiveMinORBConfirmationStrat",
]
