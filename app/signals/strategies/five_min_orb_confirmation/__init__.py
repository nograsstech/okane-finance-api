"""
5-minute Opening Range Breakout strategies module - Version B.

Contains Version B implementation with retest confirmation.
"""
from ..five_min_orb import orb_utils
from .five_min_orb_confirmation_backtest import FiveMinORBConfirmationStrat, backtest
from .five_min_orb_confirmation_signals import five_min_orb_confirmation_signals

convert_utc_to_session_time = orb_utils.convert_utc_to_session_time
detect_session_window = orb_utils.detect_session_window
calculate_pip_value = orb_utils.calculate_pip_value
calculate_or_size_pips = orb_utils.calculate_or_size_pips
get_or_threshold = orb_utils.get_or_threshold
should_skip_session = orb_utils.should_skip_session
identify_opening_range = orb_utils.identify_opening_range

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
