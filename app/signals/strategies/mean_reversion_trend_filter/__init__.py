"""
Mean Reversion + Trend Filter Strategy

This strategy combines mean reversion entries with a higher-timeframe trend filter.
- 4H timeframe: Trend filter using EMA 200
- 1H timeframe: Entry signals using pullback to EMA 50

Entry Rules (Long):
1. 4H price > 200 EMA (uptrend)
2. 1H price within 1×ATR of 50 EMA (pullback zone)
3. RSI between 35-50 (oversold but not extreme)
4. Price >= VWAP
5. Bullish engulfing OR hammer candle triggers entry

Entry Rules (Short):
1. 4H price < 200 EMA (downtrend)
2. 1H price within 1×ATR of 50 EMA (pullback zone)
3. RSI between 50-65 (overbought but not extreme)
4. Price <= VWAP
5. Bearish engulfing OR shooting star candle triggers entry

Exit Rules:
- Stop Loss: 1.5×ATR from entry (default)
- Take Profit: 2×ATR from entry (default, single exit)
"""

from .mean_reversion_trend_filter_signals import mean_reversion_trend_filter_signals
from .mean_reversion_trend_filter_backtest import backtest

__all__ = ['mean_reversion_trend_filter_signals', 'backtest']
