"""
Mean Reversion + Trend Filter Combo Strategy.

A multi-timeframe trading strategy that combines trend following with mean reversion.
Trades pullbacks in the direction of the higher timeframe trend.
"""

from .mean_reversion_trend_filter import mean_reversion_trend_filter_signals

__all__ = ['mean_reversion_trend_filter_signals']
