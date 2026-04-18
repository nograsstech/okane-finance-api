"""
ORB Autoresearch Backtest.

Uses the picklable class-variable injection pattern (Version A) for
multiprocessing compatibility.

SL/TP are computed inside next() using tunable class attributes so that
bt.optimize() can explore narrow_threshold, sl_narrow_fraction, tp_multiplier
without re-running signal generation.
"""

import logging
import multiprocessing as mp
import time as _time

import numpy as np
from backtesting import Backtest, Strategy

logger = logging.getLogger(__name__)

if mp.get_start_method(allow_none=True) != "fork":
    mp.set_start_method("fork", force=True)


class ORBAutoresearchStrat(Strategy):
    """
    ORB Autoresearch strategy class (module-level for multiprocessing pickling).

    Indicator data is injected via class variables before each backtest run.
    SL/TP are computed per-bar using tunable attrs so bt.optimize() can sweep them.
    """

    # Tunable parameters (swept by bt.optimize)
    narrow_threshold = 0.002      # range_pct < this → narrow classification
    sl_narrow_fraction = 0.6667   # SL placed this fraction into range for narrow (2/3)
    tp_multiplier = 1.0           # TP = entry ± range_height * tp_multiplier

    # Fixed runtime attrs
    mysize = 0.03
    record_trades = False
    trades_actions = []

    # Injected indicator data (set before run)
    _signal_data = None
    _or_high_data = None
    _or_low_data = None
    _or_range_pct_data = None
    _session_active_data = None

    def init(self):
        super().init()
        if self._signal_data is not None:
            self.signal1 = self.I(lambda: self.__class__._signal_data)
        if self._or_high_data is not None:
            self.or_high = self.I(lambda: self.__class__._or_high_data)
        if self._or_low_data is not None:
            self.or_low = self.I(lambda: self.__class__._or_low_data)
        if self._or_range_pct_data is not None:
            self.or_range_pct = self.I(lambda: self.__class__._or_range_pct_data)
        if self._session_active_data is not None:
            self.session_active = self.I(lambda: self.__class__._session_active_data)

    def next(self):
        super().next()

        # Close any open position when session ends
        sess_active = self.session_active[-1] if hasattr(self, "session_active") else True
        if not sess_active and self.position:
            self.position.close()
            return

        signal = self.signal1[-1]
        or_high = self.or_high[-1]
        or_low = self.or_low[-1]
        or_range_pct = self.or_range_pct[-1]

        if signal == 0:
            return
        if np.isnan(or_high) or np.isnan(or_low) or np.isnan(or_range_pct):
            return
        if len(self.trades) > 0:
            return

        range_height = or_high - or_low
        if range_height <= 0:
            return

        is_narrow = or_range_pct < self.__class__.narrow_threshold
        current_price = self.data.Close[-1]

        if signal == 2:
            # Long entry
            if is_narrow:
                sl = or_low + self.__class__.sl_narrow_fraction * range_height
            else:
                sl = or_low
            tp = current_price + range_height * self.__class__.tp_multiplier

            if sl >= current_price or tp <= current_price:
                return

            self.buy(sl=sl, tp=tp, size=self.__class__.mysize)

            if self.__class__.record_trades:
                self.__class__.trades_actions.append({
                    "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "trade_action": "buy",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl,
                    "tp": tp,
                    "size": self.__class__.mysize,
                })

        elif signal == 1:
            # Short entry
            if is_narrow:
                sl = or_high - self.__class__.sl_narrow_fraction * range_height
            else:
                sl = or_high
            tp = current_price - range_height * self.__class__.tp_multiplier

            if sl <= current_price or tp >= current_price:
                return

            self.sell(sl=sl, tp=tp, size=self.__class__.mysize)

            if self.__class__.record_trades:
                self.__class__.trades_actions.append({
                    "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "trade_action": "sell",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl,
                    "tp": tp,
                    "size": self.__class__.mysize,
                })


def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    """
    Run backtest for ORB Autoresearch strategy.

    Args:
        df: DataFrame with OHLCV data and ORB signal columns produced by
            orb_autoresearch_signals (TotalSignal, OR_High, OR_Low, OR_Range_Pct,
            Session_Active).
        strategy_parameters: Dict of strategy parameters.
        size: Position size (default: 0.03).
        skip_optimization: If True, use best_params directly.
        best_params: Pre-optimized parameters dict with keys:
            - narrow_threshold, sl_narrow_fraction, tp_multiplier

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    t_start = _time.time()

    if df is None or df.empty:
        return None, None, [], {}

    required = ["TotalSignal", "OR_High", "OR_Low", "OR_Range_Pct", "Session_Active"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("[ORB autoresearch backtest] Missing columns: %s", missing)
        return None, None, [], {}

    logger.debug(
        "[ORB autoresearch backtest] rows=%d signals=%d",
        len(df), int((df["TotalSignal"] != 0).sum()),
    )

    dftest = df.copy()
    params = strategy_parameters.copy() if strategy_parameters else {}

    or_high_arr = dftest["OR_High"].astype(float).values
    or_low_arr = dftest["OR_Low"].astype(float).values
    or_range_pct_arr = dftest["OR_Range_Pct"].astype(float).values
    session_active_arr = dftest["Session_Active"].astype(float).values

    ORBAutoresearchStrat._signal_data = dftest["TotalSignal"]
    ORBAutoresearchStrat._or_high_data = or_high_arr
    ORBAutoresearchStrat._or_low_data = or_low_arr
    ORBAutoresearchStrat._or_range_pct_data = or_range_pct_arr
    ORBAutoresearchStrat._session_active_data = session_active_arr

    cash = 100_000
    margin = 1 / 500
    lot_size = size

    ORBAutoresearchStrat.mysize = lot_size
    ORBAutoresearchStrat.narrow_threshold = params.get("narrow_threshold", 0.002)
    ORBAutoresearchStrat.sl_narrow_fraction = params.get("sl_narrow_fraction", 0.6667)
    ORBAutoresearchStrat.tp_multiplier = params.get("tp_multiplier", 1.0)
    ORBAutoresearchStrat.trades_actions = []

    if not skip_optimization:
        t_opt = _time.time()
        logger.debug("[ORB autoresearch backtest] Starting optimization (3×3×3 = 27 combos)...")
        bt = Backtest(dftest, ORBAutoresearchStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            narrow_threshold=[0.0015, 0.002, 0.0025],
            sl_narrow_fraction=[0.5, 0.6667, 0.8],
            tp_multiplier=[1.0, 1.25, 1.5],
            maximize="Sharpe Ratio",
            max_tries=27,
            random_state=0,
            return_heatmap=True,
        )
        logger.debug("[ORB autoresearch backtest] Optimization done in %.1fs", _time.time() - t_opt)

        heatmap_df = heatmap.unstack()
        max_value = heatmap_df.max().max()
        optimized_params = (heatmap_df == max_value).stack().idxmax()

        best_params = {
            "narrow_threshold": optimized_params[0],
            "sl_narrow_fraction": optimized_params[1],
            "tp_multiplier": optimized_params[2],
        }
        logger.debug("[ORB autoresearch backtest] Best params: %s", best_params)
    else:
        defaults = {
            "narrow_threshold": 0.002,
            "sl_narrow_fraction": 0.6667,
            "tp_multiplier": 1.0,
        }
        best_params = {**defaults, **(best_params or {})}
        logger.debug("[ORB autoresearch backtest] Skipping optimization, params: %s", best_params)

    strategy_parameters = {
        "best": True,
        "narrow_threshold": best_params["narrow_threshold"],
        "sl_narrow_fraction": best_params["sl_narrow_fraction"],
        "tp_multiplier": best_params["tp_multiplier"],
    }

    ORBAutoresearchStrat.narrow_threshold = strategy_parameters["narrow_threshold"]
    ORBAutoresearchStrat.sl_narrow_fraction = strategy_parameters["sl_narrow_fraction"]
    ORBAutoresearchStrat.tp_multiplier = strategy_parameters["tp_multiplier"]
    ORBAutoresearchStrat.record_trades = True
    ORBAutoresearchStrat.trades_actions = []

    t_final = _time.time()
    bt_best = Backtest(dftest, ORBAutoresearchStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = list(bt_best._strategy.trades_actions)

    logger.debug(
        "[ORB autoresearch backtest] Final run done in %.1fs — trades=%s, actions=%d | total=%.1fs",
        _time.time() - t_final,
        stats["# Trades"],
        len(trades_actions),
        _time.time() - t_start,
    )

    # Prevent state leakage across calls
    ORBAutoresearchStrat._signal_data = None
    ORBAutoresearchStrat._or_high_data = None
    ORBAutoresearchStrat._or_low_data = None
    ORBAutoresearchStrat._or_range_pct_data = None
    ORBAutoresearchStrat._session_active_data = None

    return bt_best, stats, trades_actions, strategy_parameters
