"""
strategy.py — Opening Range Breakout strategy implementation.
THIS IS THE ONLY FILE THE AGENT MODIFIES.

The agent may freely change:
  - ORB parameters (opening_range_minutes, breakout_threshold, etc.)
  - Entry/exit logic
  - Stop loss and take profit rules
  - Time filters (session hours, day-of-week)
  - Position sizing
  - Any other strategy logic

The agent may NOT:
  - Modify prepare.py
  - Change the metric computation logic
  - Add external data sources outside of Yahoo Finance
  - Change the symbols list (defined in prepare.py)

Goal: MAXIMIZE mean_sharpe across all symbols on in-sample data.
      We care about robustness (consistent across symbols), not curve-fitting one pair.
"""

import sys
import os
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# Import fixed infrastructure (do not modify)
sys.path.insert(0, os.path.dirname(__file__))
from prepare import (
    load_data, split_train_test, compute_metrics,
    save_results, print_summary, ALL_SYMBOLS,
    LOGS_DIR
)

# ─── Strategy Parameters (agent modifies these) ──────────────────────────────

PARAMS = {
    # Opening range duration (bars). With 5m bars: 6 bars = 30 minutes.
    # The first N bars after session open are observation-only; trade starts after.
    "opening_range_bars": 6,

    # Breakout threshold: 0.001 = 0.1%
    "breakout_threshold": 0.001,

    # Stop loss as fraction of the opening range height.
    "stop_loss_range_multiple": 1.8,

    # Take profit as fraction of the opening range height.
    "take_profit_range_multiple": 1.0,

    # Maximum number of trades per session per symbol (0 = unlimited)
    "max_trades_per_session": 1,

    # Minimum range height as fraction of price (0 = no filter).
    "min_range_pct": 0.0,

    # Close all positions at session end (True = no overnight holds)
    "close_at_session_end": True,

    # Day-of-week filter: list of allowed weekdays (0=Mon, 4=Fri)
    "allowed_weekdays": [1, 2, 3, 4],  # Tue–Fri (skip choppy Monday)

    # Sessions: list of (start_hour_utc, start_minute_utc, end_hour_utc, end_minute_utc)
    # London: 08:00–12:30 UTC  |  New York: 13:30–20:00 UTC
    "sessions": [
        (8,  0,  12, 30),   # London
        (13, 30, 20, 0),    # New York
    ],
}

# ─── ORB Strategy Class ───────────────────────────────────────────────────────

def _session_key(dt, sessions):
    """Return (start_h, start_m) key of the active session for dt, or None."""
    for (sh, sm, eh, em) in sessions:
        session_start = dt.replace(hour=sh, minute=sm, second=0, microsecond=0)
        session_end   = dt.replace(hour=eh, minute=em, second=0, microsecond=0)
        if session_start <= dt < session_end:
            return (sh, sm)
    return None


class ORBStrategy(Strategy):
    """
    Dual-session Opening Range Breakout (5m bars).

    Logic:
    1. Two sessions per day: London (08:00–12:30 UTC) and New York (13:30–20:00 UTC).
    2. First `opening_range_bars` bars (default 3 = 15 min) after each session open:
       observe only, build the opening range High/Low. Do NOT trade yet.
    3. After range is set, trade breakouts above range_high or below range_low.
    4. Stop loss and take profit based on range height multiples.
    5. Close all open trades at session end. Reset range state for next session.
    """

    opening_range_bars         = PARAMS["opening_range_bars"]
    breakout_threshold         = PARAMS["breakout_threshold"]
    stop_loss_range_multiple   = PARAMS["stop_loss_range_multiple"]
    take_profit_range_multiple = PARAMS["take_profit_range_multiple"]
    max_trades_per_session     = PARAMS["max_trades_per_session"]
    min_range_pct              = PARAMS["min_range_pct"]
    close_at_session_end       = PARAMS["close_at_session_end"]

    def init(self):
        self._active_session   = None   # (start_h, start_m) key
        self._session_open_bar = None   # bar index when session started
        self._range_high       = None
        self._range_low        = None
        self._range_set        = False
        self._trades_this_session = 0

    def next(self):
        current_time = self.data.index[-1]

        # ── Skip disallowed weekdays ──────────────────────────────────────
        if current_time.weekday() not in PARAMS["allowed_weekdays"]:
            return

        sessions = PARAMS["sessions"]
        sess_key = _session_key(current_time, sessions)

        # ── Between sessions: close any open position ─────────────────────
        if sess_key is None:
            if self.close_at_session_end and self.position:
                self.position.close()
            return

        # ── New session started: reset range state ────────────────────────
        if sess_key != self._active_session:
            # Close leftover position from previous session
            if self.close_at_session_end and self.position:
                self.position.close()
            self._active_session      = sess_key
            self._session_open_bar    = len(self.data) - 1
            self._range_high          = None
            self._range_low           = None
            self._range_set           = False
            self._trades_this_session = 0

        # ── Formation window: observe only, no trades ─────────────────────
        bars_into_session = len(self.data) - 1 - self._session_open_bar
        if not self._range_set:
            if bars_into_session < self.opening_range_bars:
                return  # Still forming the opening range — do nothing
            # Range complete: capture High/Low of the formation bars
            range_slice_high = self.data.High[-self.opening_range_bars - 1 : -1]
            range_slice_low  = self.data.Low[-self.opening_range_bars - 1 : -1]
            self._range_high = float(max(range_slice_high))
            self._range_low  = float(min(range_slice_low))
            self._range_set  = True

        if self._range_high is None or self._range_low is None:
            return

        range_height = self._range_high - self._range_low
        if range_height <= 0:
            return

        # ── Minimum range filter ──────────────────────────────────────────
        range_mid = (self._range_high + self._range_low) / 2
        if self.min_range_pct > 0 and range_height / range_mid < self.min_range_pct:
            return

        # ── Per-session trade limit ───────────────────────────────────────
        if self.max_trades_per_session > 0 and self._trades_this_session >= self.max_trades_per_session:
            return

        # ── Time filter: only trade within 50 min (10 bars) after range forms ──
        bars_since_range = bars_into_session - self.opening_range_bars
        if bars_since_range < 2 or bars_since_range > 10:
            return

        # ── Entry signals ─────────────────────────────────────────────────
        close = self.data.Close[-1]
        sl_dist   = range_height * self.stop_loss_range_multiple
        tp_dist   = range_height * self.take_profit_range_multiple

        long_trigger  = self._range_high * (1 + self.breakout_threshold)
        short_trigger = self._range_low  * (1 - self.breakout_threshold)

        if not self.position:
            range_mid = (self._range_high + self._range_low) / 2
            narrow_range = range_height / range_mid < 0.002
            long_sl = (self._range_low + 2 * range_height / 3) if narrow_range else self._range_low
            short_sl = (self._range_high - 2 * range_height / 3) if narrow_range else self._range_high
            is_london = sess_key == (8, 0)
            is_ny = sess_key == (13, 30)
            if close > long_trigger and not (is_ny and narrow_range):
                self.buy(sl=long_sl, tp=close + tp_dist)
                self._trades_this_session += 1
            elif close < short_trigger and not (is_london and narrow_range):
                self.sell(sl=short_sl, tp=close - tp_dist)
                self._trades_this_session += 1


# ─── Run Backtest ─────────────────────────────────────────────────────────────

def run_experiment(tag: str, params: dict = None, optimize: bool = False):
    """
    Run backtest on all symbols, collect metrics, save results.

    Args:
        tag:      Short label for this experiment run (e.g. "baseline", "apr5_v1")
        params:   Override PARAMS dict (if None, uses module-level PARAMS)
        optimize: If True, run backtesting.py's optimizer on IS data before final evaluation
    """
    params = params or PARAMS
    data_all = load_data()

    metrics_by_symbol = {}

    for sym in ALL_SYMBOLS:
        df = data_all.get(sym)
        if df is None or df.empty:
            print(f"  [SKIP] {sym}: no data")
            continue

        # Flatten multi-level columns if present (yfinance quirk)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Rename to backtesting.py expected format
        df = df.rename(columns={
            "Open": "Open", "High": "High", "Low": "Low",
            "Close": "Close", "Volume": "Volume"
        })
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        # Strip timezone info (backtesting.py doesn't handle tz-aware indexes)
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        if len(df) < 50:
            print(f"  [SKIP] {sym}: insufficient data ({len(df)} rows)")
            continue

        train_df, test_df = split_train_test(df)

        # If train split is empty (data < OOS window), use all data for training
        if len(train_df) < 50:
            train_df = df

        # ── Set class-level params ────────────────────────────────────────
        ORBStrategy.opening_range_bars         = params["opening_range_bars"]
        ORBStrategy.breakout_threshold         = params["breakout_threshold"]
        ORBStrategy.stop_loss_range_multiple   = params["stop_loss_range_multiple"]
        ORBStrategy.take_profit_range_multiple = params["take_profit_range_multiple"]
        ORBStrategy.max_trades_per_session     = params["max_trades_per_session"]
        ORBStrategy.min_range_pct              = params["min_range_pct"]
        ORBStrategy.close_at_session_end       = params["close_at_session_end"]

        try:
            bt = Backtest(
                train_df,
                ORBStrategy,
                cash=100_000,
                commission=0.0002,   # 2 bps (realistic for forex/CFD)
                exclusive_orders=True,
            )

            if optimize:
                stats = bt.optimize(
                    opening_range_bars        = [1, 2, 3, 4],
                    breakout_threshold        = [0.0, 0.001, 0.002],
                    stop_loss_range_multiple  = [0.3, 0.5, 0.75, 1.0],
                    take_profit_range_multiple= [1.0, 1.5, 2.0, 3.0],
                    maximize="Sharpe Ratio",
                    max_tries=200,
                )
            else:
                stats = bt.run()

            # Extract equity curve
            equity = stats["_equity_curve"]["Equity"]

            m = compute_metrics(equity)
            m["num_trades"] = int(stats.get("# Trades", 0))
            m["win_rate"]   = round(float(stats.get("Win Rate [%]", 0)) / 100, 4)

            metrics_by_symbol[sym] = m

        except Exception as e:
            print(f"  [ERR]  {sym}: {e}")
            metrics_by_symbol[sym] = {
                "sharpe_ratio": -999.0, "max_drawdown_pct": -999.0,
                "total_return_pct": -999.0, "calmar_ratio": -999.0,
                "num_trades": 0, "win_rate": 0.0, "error": str(e),
            }

    print_summary(tag, metrics_by_symbol, params)
    save_results(tag, metrics_by_symbol, params)
    return metrics_by_symbol


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, datetime

    parser = argparse.ArgumentParser(description="ORB Autoresearch — single experiment run")
    parser.add_argument("--tag",      default=None, help="Experiment tag (default: date-based)")
    parser.add_argument("--optimize", action="store_true", help="Run backtesting.py optimizer on IS data")
    args = parser.parse_args()

    tag = args.tag or datetime.datetime.now().strftime("%Y%m%d_%H%M")
    run_experiment(tag=tag, optimize=args.optimize)
