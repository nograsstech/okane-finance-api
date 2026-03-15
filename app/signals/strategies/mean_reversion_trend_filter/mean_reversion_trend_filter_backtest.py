"""
Backtest implementation for Mean Reversion + Trend Filter Combo Strategy.

Strategy class with custom two-tier exit logic:
- TP1: Close 50% at 1.5x ATR, move SL to breakeven
- TP2: Close remaining at 3x ATR or after 10 candles
"""

import multiprocessing as mp
from backtesting import Strategy, Backtest
import pandas as pd

# Ensure fork start method for multiprocessing
if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


class MeanReversionTrendFilterStrat(Strategy):
    """
    Mean Reversion + Trend Filter strategy with two-tier exits.

    Entry:
    - Long: Signal 2 with all conditions met
    - Short: Signal 1 with all conditions met

    Exit:
    - TP1: Close 50% at 1.5x ATR, move SL to breakeven
    - TP2: Close remaining at 3x ATR
    - Time exit: 10 candles maximum hold
    - RSI exit: RSI > 70 for long, RSI < 30 for short
    """

    mysize = 0.01        # 1% position size
    slcoef = 1.5         # Stop loss = 1.5x ATR
    trades_actions = []  # List to track all trade actions

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)

    def next(self):
        super().next()

        current_atr = self.data.ATR[-1]
        current_price = self.data.Close[-1]

        # ========== Exit Logic ==========

        for trade in self.trades:
            candles_held = len(self.data) - trade.entry_bar

            # Calculate profit/loss as percentage
            pl_pct = trade.pl_pct

            if trade.is_long:
                # Long position exits

                # RSI overbought exit
                if self.data.RSI[-1] >= 70:
                    trade.close()
                    self._log_trade_action("close", trade.entry_price, current_price, None, None)
                    continue

                # TP1: Close 50% at 1.5x ATR profit
                tp1_price = trade.entry_price + (1.5 * current_atr)
                if current_price >= tp1_price:
                    if not hasattr(trade, 'tp1_hit'):
                        # Close 50% of position
                        close_size = float(trade.size) * 0.5
                        trade.close(size=close_size)
                        trade.tp1_hit = True
                        self._log_trade_action("close_partial_tp1", trade.entry_price, current_price, None, None)

                # TP2: Close remaining at 3x ATR or 10 candle max
                tp2_price = trade.entry_price + (3.0 * current_atr)
                if current_price >= tp2_price or candles_held >= 10:
                    trade.close()
                    self._log_trade_action("close_tp2", trade.entry_price, current_price, None, None)

            elif trade.is_short:
                # Short position exits

                # RSI oversold exit
                if self.data.RSI[-1] <= 30:
                    trade.close()
                    self._log_trade_action("close", trade.entry_price, current_price, None, None)
                    continue

                # TP1: Close 50% at 1.5x ATR profit
                tp1_price = trade.entry_price - (1.5 * current_atr)
                if current_price <= tp1_price:
                    if not hasattr(trade, 'tp1_hit'):
                        # Close 50% of position
                        close_size = float(trade.size) * 0.5
                        trade.close(size=close_size)
                        trade.tp1_hit = True
                        self._log_trade_action("close_partial_tp1", trade.entry_price, current_price, None, None)

                # TP2: Close remaining at 3x ATR or 10 candle max
                tp2_price = trade.entry_price - (3.0 * current_atr)
                if current_price <= tp2_price or candles_held >= 10:
                    trade.close()
                    self._log_trade_action("close_tp2", trade.entry_price, current_price, None, None)

        # ========== Entry Logic ==========

        # Only enter if no existing positions
        if len(self.trades) > 0:
            return

        slatr = self.slcoef * current_atr

        if self.signal1[-1] == 2:
            # Long entry
            sl = current_price - slatr
            tp1 = current_price + (1.5 * current_atr)  # TP1 at 1.5x ATR
            tp2 = current_price + (3.0 * current_atr)  # TP2 at 3x ATR

            self.buy(sl=sl, size=self.mysize)
            self._log_trade_action("buy", current_price, current_price, sl, tp1)

        elif self.signal1[-1] == 1:
            # Short entry
            sl = current_price + slatr
            tp1 = current_price - (1.5 * current_atr)  # TP1 at 1.5x ATR
            tp2 = current_price - (3.0 * current_atr)  # TP2 at 3x ATR

            self.sell(sl=sl, size=self.mysize)
            self._log_trade_action("sell", current_price, current_price, sl, tp1)

    def _log_trade_action(self, action, entry_price, price, sl, tp):
        """Log trade action to trades_actions list."""
        if _strategy_parameters and _strategy_parameters.get('best', False):
            action_type = action
            if action.startswith("close_partial"):
                action_type = "close_partial"

            self.trades_actions.append({
                "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                "trade_action": action_type,
                "entry_price": entry_price,
                "price": price,
                "sl": sl,
                "tp": tp,
                "size": self.mysize,
            })


def backtest(
    df,
    strategy_parameters,
    size=0.01,
    skip_optimization=False,
    best_params=None
):
    """
    Run backtest for the Mean Reversion + Trend Filter strategy.

    Args:
        df: DataFrame with OHLCV data and TotalSignal column
        strategy_parameters: Dict of strategy parameters
        size: Position size (default 0.01 = 1%)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("mean_reversion_trend_filter backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1 / 500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    MeanReversionTrendFilterStrat.mysize = lot_size
    MeanReversionTrendFilterStrat.slcoef = strategy_parameters.get("slcoef", 1.5)
    MeanReversionTrendFilterStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing mean_reversion_trend_filter...")
        bt = Backtest(dftest, MeanReversionTrendFilterStrat, cash=cash, margin=margin, finalize_trades=True)

        # Optimize slcoef only (TP distances are fixed by strategy design)
        stats, heatmap = bt.optimize(
            slcoef=[1.0, 1.5, 2.0],  # Stop loss coefficient
            maximize="Win Rate [%]",
            max_tries=100,
            random_state=0,
            return_heatmap=True,
        )

        # Find best parameters
        if isinstance(heatmap, pd.Series):
            best_slcoef = heatmap.idxmax()
        else:
            # Handle multi-index case
            best_slcoef = heatmap.unstack().idxmax()

        # Extract the actual value from tuple if needed
        if isinstance(best_slcoef, tuple):
            best_slcoef = float(best_slcoef[0])
        else:
            best_slcoef = float(best_slcoef)

        best_params = {
            'slcoef': best_slcoef,
            'size': lot_size
        }

        print(f"Optimized parameters: {best_params}")
    else:
        # Use provided best_params or defaults
        if best_params is None:
            best_params = {
                'slcoef': 1.5,
                'size': lot_size
            }
        print("Optimization is skipped, using params:", best_params)

    # Final strategy parameters
    strategy_parameters = {
        "best": True,
        "slcoef": best_params.get('slcoef', 1.5),
        "size": best_params.get('size', lot_size)
    }

    print("Final strategy parameters:", strategy_parameters)

    # Update class with final parameters
    MeanReversionTrendFilterStrat.slcoef = strategy_parameters["slcoef"]
    _strategy_parameters = strategy_parameters

    # Run final backtest
    bt_best = Backtest(dftest, MeanReversionTrendFilterStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
