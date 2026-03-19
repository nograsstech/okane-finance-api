"""
5-Minute Opening Range Breakout (ORB) Backtest - Version B.

Version B: Breakout with retest confirmation
- Waits for price to retest OR level after breakout
- Tighter stop loss (3-5 pips from OR level)
- Higher TP targets (1.5× and 2.5× OR size)
- Entry on confirmation (close or rejection wick)
"""

from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp
import numpy as np

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


def OR_HIGH():
    """Return the OR_High column from the test DataFrame."""
    return _dftest.OR_High


def OR_LOW():
    """Return the OR_Low column from the test DataFrame."""
    return _dftest.OR_Low


def OR_SIZE_PIPS():
    """Return the OR_Size_Pips column from the test DataFrame."""
    return _dftest.OR_Size_Pips


def PIP_VALUE():
    """Return the pip value for the instrument."""
    pip_val = getattr(_dftest.Pip_Value, 'iloc', None)
    if pip_val is not None:
        return pip_val.iloc[0]
    return _dftest.Pip_Value.iloc[0]


class FiveMinORBConfirmationStrat(Strategy):
    """5-Minute ORB Strategy with retest confirmation."""

    mysize = 0.03
    sl_buffer_pips = 4  # Tighter stop (3-5 pips from OR level)
    tp1_multiplier = 1.5  # Higher TP (1.5× OR size)
    tp2_multiplier = 2.5  # Higher TP (2.5× OR size)
    trades_actions = []

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)
        self.or_high = self.I(OR_HIGH)
        self.or_low = self.I(OR_LOW)
        self.or_size_pips = self.I(OR_SIZE_PIPS)

    def next(self):
        super().next()

        # Get current values
        or_high = self.or_high[-1]
        or_low = self.or_low[-1]
        or_size_pips = self.or_size_pips[-1]
        pip_value = PIP_VALUE()

        # Skip if OR data is not available
        if or_high is None or or_low is None or or_size_pips is None:
            return

        # Check for NaN values
        if np.isnan(or_high) or np.isnan(or_low) or np.isnan(or_size_pips):
            return

        # Entry conditions
        if self.signal1 == 2 and len(self.trades) == 0:
            # Long entry - SL placed below OR High (now acts as support)
            sl_price = or_high - (self.sl_buffer_pips * pip_value)
            tp1_price = or_high + (or_size_pips * pip_value * self.tp1_multiplier)
            tp2_price = or_high + (or_size_pips * pip_value * self.tp2_multiplier)

            # Enter with 50% position at each TP level
            size1 = self.mysize * 0.5
            size2 = self.mysize * 0.5

            # Enter first half with TP1
            self.buy(sl=sl_price, tp=tp1_price, size=size1)

            # Enter second half with TP2
            self.buy(sl=sl_price, tp=tp2_price, size=size2)

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl_price,
                    "tp": f"TP1: {tp1_price}, TP2: {tp2_price}",
                    "size": self.mysize,
                })

        elif self.signal1 == 1 and len(self.trades) == 0:
            # Short entry - SL placed above OR Low (now acts as resistance)
            sl_price = or_low + (self.sl_buffer_pips * pip_value)
            tp1_price = or_low - (or_size_pips * pip_value * self.tp1_multiplier)
            tp2_price = or_low - (or_size_pips * pip_value * self.tp2_multiplier)

            # Enter with 50% position at each TP level
            size1 = self.mysize * 0.5
            size2 = self.mysize * 0.5

            # Enter first half with TP1
            self.sell(sl=sl_price, tp=tp1_price, size=size1)

            # Enter second half with TP2
            self.sell(sl=sl_price, tp=tp2_price, size=size2)

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl_price,
                    "tp": f"TP1: {tp1_price}, TP2: {tp2_price}",
                    "size": self.mysize,
                })


def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    """
    Run backtest for the 5-Minute ORB strategy (Version B).

    Args:
        df: DataFrame with OHLCV data and ORB signal columns (OR_High, OR_Low,
            OR_Size_Pips, Pip_Value, TotalSignal)
        strategy_parameters: Dict of strategy parameters
        size: Position size (default: 0.03)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict with keys:
            - sl_buffer_pips: Buffer for SL from OR level (default: 4)
            - tp1_multiplier: TP1 as multiple of OR size (default: 1.5)
            - tp2_multiplier: TP2 as multiple of OR size (default: 2.5)

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("five_min_orb_confirmation backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters.copy() if strategy_parameters else {}

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    FiveMinORBConfirmationStrat.mysize = lot_size
    FiveMinORBConfirmationStrat.sl_buffer_pips = _strategy_parameters.get("sl_buffer_pips", 4)
    FiveMinORBConfirmationStrat.tp1_multiplier = _strategy_parameters.get("tp1_multiplier", 1.5)
    FiveMinORBConfirmationStrat.tp2_multiplier = _strategy_parameters.get("tp2_multiplier", 2.5)
    FiveMinORBConfirmationStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing five_min_orb_confirmation...")
        bt = Backtest(dftest, FiveMinORBConfirmationStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            sl_buffer_pips=[3, 4, 5],
            tp1_multiplier=[i / 10 for i in range(12, 19, 3)],  # 1.2, 1.5, 1.8
            tp2_multiplier=[i / 10 for i in range(20, 31, 5)],  # 2.0, 2.5, 3.0
            maximize="Win Rate [%]",
            max_tries=200,
            random_state=0,
            return_heatmap=True,
        )

        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()

        # Find the maximum value over the entire DataFrame
        max_value = heatmap_df.max().max()

        # Find the index of the maximum value
        optimized_params = (heatmap_df == max_value).stack().idxmax()

        best_params = {
            'sl_buffer_pips': optimized_params[0],
            'tp1_multiplier': optimized_params[1],
            'tp2_multiplier': optimized_params[2]
        }

        print(best_params)
    else:
        # Use provided best_params or defaults
        if best_params is None:
            best_params = {
                'sl_buffer_pips': 4,
                'tp1_multiplier': 1.5,
                'tp2_multiplier': 2.5
            }
        print("Optimization is skipped, using params:", best_params)

    strategy_parameters = {
        "best": True,
        "sl_buffer_pips": best_params['sl_buffer_pips'],
        "tp1_multiplier": best_params['tp1_multiplier'],
        "tp2_multiplier": best_params['tp2_multiplier']
    }

    print(strategy_parameters)

    FiveMinORBConfirmationStrat.sl_buffer_pips = strategy_parameters["sl_buffer_pips"]
    FiveMinORBConfirmationStrat.tp1_multiplier = strategy_parameters["tp1_multiplier"]
    FiveMinORBConfirmationStrat.tp2_multiplier = strategy_parameters["tp2_multiplier"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    bt_best = Backtest(dftest, FiveMinORBConfirmationStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
