"""
5-Minute Opening Range Breakout (ORB) Backtest - Version A.

Version A: Immediate breakout entry
- Enters on breakouts from the opening range
- Stop loss placed beyond OR levels
- Take profit targets at 1× and 2× OR size
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
    # Pip_Value is a scalar or series - access first element if series
    if hasattr(_dftest.Pip_Value, 'iloc'):
        return _dftest.Pip_Value.iloc[0]
    return _dftest.Pip_Value


class FiveMinORBStrat(Strategy):
    """5-Minute ORB Strategy with immediate breakout entry."""

    mysize = 0.03
    spread_buffer_pips = 2
    tp1_multiplier = 1.0
    tp2_multiplier = 2.0
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

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": f"TP1: {tp1_price}, TP2: {tp2_price}",
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

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": f"TP1: {tp1_price}, TP2: {tp2_price}",
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
    import time as _time
    global _dftest, _strategy_parameters

    t_start = _time.time()

    # Validate input data
    if df is None or df.empty:
        print("five_min_orb backtest: df is None or empty")
        return None, None, [], {}

    print(f"[ORB backtest] DataFrame rows: {len(df)}, signals: {(df.get('TotalSignal', 0) != 0).sum()}")

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters.copy() if strategy_parameters else {}

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    FiveMinORBStrat.mysize = lot_size
    FiveMinORBStrat.spread_buffer_pips = _strategy_parameters.get("spread_buffer_pips", 2)
    FiveMinORBStrat.tp1_multiplier = _strategy_parameters.get("tp1_multiplier", 1.0)
    FiveMinORBStrat.tp2_multiplier = _strategy_parameters.get("tp2_multiplier", 2.0)
    FiveMinORBStrat.trades_actions = []

    # Skip optimization — use provided best_params or defaults
    if best_params is None:
        best_params = {
            'spread_buffer_pips': 2,
            'tp1_multiplier': 1.0,
            'tp2_multiplier': 2.0
        }
    print("[ORB backtest] Using params:", best_params)

    strategy_parameters = {
        "best": True,
        "spread_buffer_pips": best_params['spread_buffer_pips'],
        "tp1_multiplier": best_params['tp1_multiplier'],
        "tp2_multiplier": best_params['tp2_multiplier']
    }

    print(strategy_parameters)

    FiveMinORBStrat.spread_buffer_pips = strategy_parameters["spread_buffer_pips"]
    FiveMinORBStrat.tp1_multiplier = strategy_parameters["tp1_multiplier"]
    FiveMinORBStrat.tp2_multiplier = strategy_parameters["tp2_multiplier"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    t_final = _time.time()
    print("[ORB backtest] Running final backtest with best params...")
    bt_best = Backtest(dftest, FiveMinORBStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions
    print(f"[ORB backtest] Final run done in {_time.time() - t_final:.1f}s — trades: {stats['# Trades']}, actions: {len(trades_actions)}")
    print(f"[ORB backtest] Total backtest time: {_time.time() - t_start:.1f}s")

    return bt_best, stats, trades_actions, strategy_parameters
