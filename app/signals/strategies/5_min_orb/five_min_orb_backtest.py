"""
5-Minute Opening Range Breakout (ORB) Backtest - Version A.

Version A: Immediate breakout entry
- Enters on breakouts from the opening range
- Stop loss placed beyond OR levels
- Take profit targets at 1× and 2× OR size
"""

from backtesting import Strategy
from backtesting import Backtest
import logging
import multiprocessing as mp
import numpy as np

logger = logging.getLogger(__name__)

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)


class FiveMinORBStrat(Strategy):
    """
    5-Minute ORB Strategy with immediate breakout entry.

    This class is defined at module level to be picklable for multiprocessing.
    Indicator data is passed via class variables set before backtest execution.
    """

    # Default values (will be overridden before backtest)
    mysize = 0.03
    spread_buffer_pips = 2
    tp1_multiplier = 1.0
    tp2_multiplier = 2.0
    pip_value = 1.0
    record_trades = False
    trades_actions = []

    # Class variables to hold indicator data (set before backtest)
    _signal_data = None
    _or_high_data = None
    _or_low_data = None
    _or_size_pips_data = None

    def init(self):
        super().init()
        # Use class-level data if available, otherwise use indicator wrapper
        if self._signal_data is not None:
            self.signal1 = self.I(lambda: self._signal_data)
        if self._or_high_data is not None:
            self.or_high = self.I(lambda: self._or_high_data)
        if self._or_low_data is not None:
            self.or_low = self.I(lambda: self._or_low_data)
        if self._or_size_pips_data is not None:
            self.or_size_pips = self.I(lambda: self._or_size_pips_data)

    def next(self):
        super().next()

        # Get current values
        or_high = self.or_high[-1]
        or_low = self.or_low[-1]
        or_size_pips = self.or_size_pips[-1]
        pip_value = self.__class__.pip_value

        # Skip if OR data is not available
        if or_high is None or or_low is None or or_size_pips is None:
            return

        # Check for NaN values
        if np.isnan(or_high) or np.isnan(or_low) or np.isnan(or_size_pips):
            return

        # Entry conditions
        current_price = self.data.Close[-1]

        if self.signal1 == 2 and len(self.trades) == 0:
            # Long entry
            sl_price = or_low - (self.spread_buffer_pips * pip_value)
            tp1_price = or_high + (or_size_pips * pip_value * self.tp1_multiplier)
            tp2_price = or_high + (or_size_pips * pip_value * self.tp2_multiplier)

            # Validate: SL < entry < TP (skip if price already past TP)
            if sl_price >= current_price or tp1_price <= current_price:
                return

            # Enter with 50% position at each TP level
            size1 = self.mysize * 0.5
            size2 = self.mysize * 0.5

            # Enter first half with TP1
            self.buy(sl=sl_price, tp=tp1_price, size=size1)

            # Enter second half with TP2 (only if TP2 is also valid)
            if tp2_price > current_price:
                self.buy(sl=sl_price, tp=tp2_price, size=size2)

            if self.__class__.record_trades:
                self.__class__.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": tp1_price,  # Store primary TP as numeric value
                    "size": self.mysize,
                })

        elif self.signal1 == 1 and len(self.trades) == 0:
            # Short entry
            sl_price = or_high + (self.spread_buffer_pips * pip_value)
            tp1_price = or_low - (or_size_pips * pip_value * self.tp1_multiplier)
            tp2_price = or_low - (or_size_pips * pip_value * self.tp2_multiplier)

            # Validate: TP < entry < SL (skip if price already past TP)
            if sl_price <= current_price or tp1_price >= current_price:
                return

            # Enter with 50% position at each TP level
            size1 = self.mysize * 0.5
            size2 = self.mysize * 0.5

            # Enter first half with TP1
            self.sell(sl=sl_price, tp=tp1_price, size=size1)

            # Enter second half with TP2 (only if TP2 is also valid)
            if tp2_price < current_price:
                self.sell(sl=sl_price, tp=tp2_price, size=size2)

            if self.__class__.record_trades:
                self.__class__.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": tp1_price,  # Store primary TP as numeric value
                    "size": self.mysize,
                })


def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    """
    Run backtest for the 5-Minute ORB strategy (Version A).

    Args:
        df: DataFrame with OHLCV data and ORB signal columns (OR_High, OR_Low,
            OR_Size_Pips, Pip_Value, TotalSignal)
        strategy_parameters: Dict of strategy parameters
        size: Position size (default: 0.03)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict with keys:
            - spread_buffer_pips: Buffer for SL beyond OR levels
            - tp1_multiplier: TP1 as multiple of OR size (default: 1.0)
            - tp2_multiplier: TP2 as multiple of OR size (default: 2.0)

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    return _run_backtest(df, strategy_parameters, size, skip_optimization, best_params)


def _run_backtest(df, strategy_parameters, size, skip_optimization, best_params):
    """Run backtest using module-level strategy class."""
    import time as _time

    t_start = _time.time()

    # Validate input data
    if df is None or df.empty:
        return None, None, [], {}

    logger.debug("[ORB backtest] DataFrame rows: %d, signals: %d", len(df), (df.get('TotalSignal', 0) != 0).sum())

    dftest = df.copy()
    params = strategy_parameters.copy() if strategy_parameters else {}

    # Resolve pip value once (scalar) so it can be stored as a class attribute
    pip_val = dftest.Pip_Value.iloc[0] if hasattr(dftest.Pip_Value, 'iloc') else dftest.Pip_Value

    # Set indicator data as class variables (module-level class can access these)
    FiveMinORBStrat._signal_data = dftest.TotalSignal
    FiveMinORBStrat._or_high_data = dftest.OR_High
    FiveMinORBStrat._or_low_data = dftest.OR_Low
    FiveMinORBStrat._or_size_pips_data = dftest.OR_Size_Pips

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set strategy class attributes
    FiveMinORBStrat.mysize = lot_size
    FiveMinORBStrat.spread_buffer_pips = params.get("spread_buffer_pips", 2)
    FiveMinORBStrat.tp1_multiplier = params.get("tp1_multiplier", 1.0)
    FiveMinORBStrat.tp2_multiplier = params.get("tp2_multiplier", 2.0)
    FiveMinORBStrat.pip_value = pip_val
    FiveMinORBStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        t_opt = _time.time()
        logger.debug("[ORB backtest] Starting optimization (2×2×2 = 8 combos)...")
        bt = Backtest(dftest, FiveMinORBStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            spread_buffer_pips=[1, 3],
            tp1_multiplier=[0.5, 1.5],
            tp2_multiplier=[1.5, 2.5],
            maximize="Win Rate [%]",
            max_tries=8,
            random_state=0,
            return_heatmap=True,
        )
        logger.debug("[ORB backtest] Optimization done in %.1fs", _time.time() - t_opt)

        heatmap_df = heatmap.unstack()
        max_value = heatmap_df.max().max()
        optimized_params = (heatmap_df == max_value).stack().idxmax()

        best_params = {
            'spread_buffer_pips': optimized_params[0],
            'tp1_multiplier': optimized_params[1],
            'tp2_multiplier': optimized_params[2]
        }
        logger.debug("[ORB backtest] Best params: %s", best_params)
    else:
        defaults = {
            'spread_buffer_pips': 2,
            'tp1_multiplier': 1.0,
            'tp2_multiplier': 2.0
        }
        if best_params is None:
            best_params = defaults
        else:
            best_params = {**defaults, **best_params}
        logger.debug("[ORB backtest] Optimization skipped, using params: %s", best_params)

    strategy_parameters = {
        "best": True,
        "spread_buffer_pips": best_params['spread_buffer_pips'],
        "tp1_multiplier": best_params['tp1_multiplier'],
        "tp2_multiplier": best_params['tp2_multiplier']
    }

    logger.debug("[ORB backtest] Final strategy parameters: %s", strategy_parameters)

    FiveMinORBStrat.spread_buffer_pips = strategy_parameters["spread_buffer_pips"]
    FiveMinORBStrat.tp1_multiplier = strategy_parameters["tp1_multiplier"]
    FiveMinORBStrat.tp2_multiplier = strategy_parameters["tp2_multiplier"]
    FiveMinORBStrat.record_trades = True
    FiveMinORBStrat.trades_actions = []

    t_final = _time.time()
    logger.debug("[ORB backtest] Running final backtest with best params...")
    bt_best = Backtest(dftest, FiveMinORBStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions
    logger.debug(
        "[ORB backtest] Final run done in %.1fs — trades: %s, actions: %d | total: %.1fs",
        _time.time() - t_final, stats['# Trades'], len(trades_actions), _time.time() - t_start,
    )

    # Clean up class variables to avoid state leakage
    FiveMinORBStrat._signal_data = None
    FiveMinORBStrat._or_high_data = None
    FiveMinORBStrat._or_low_data = None
    FiveMinORBStrat._or_size_pips_data = None

    return bt_best, stats, trades_actions, strategy_parameters
