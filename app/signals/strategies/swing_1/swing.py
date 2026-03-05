from __future__ import annotations

import os
from typing import Optional, List, Dict
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from backtesting import Strategy

# Optional talib for candlestick pattern detection
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

# Optional matplotlib imports for plotting
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import Rectangle
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from . import constants as const
from .constants import _PAT_LABELS, _PAT_WEIGHT, BULLISH_PATTERNS, BEARISH_PATTERNS, _ZONE_COLS, _ALL_PATTERN_COLS
from .risk_manager import RiskManager


# ── Anti-clutter controls ──────────────────────────────────────────────────────
MIN_WEIGHT_TO_SHOW  = 3
MIN_BAR_GAP         = 3
# ──────────────────────────────────────────────────────────────────────────────


def identify_zones(
    df: pd.DataFrame,
    current_price: float | None = None,
    order: int = 5,
    zone_pct: float = const.SR_ZONE_THRESHOLD,
    n_bins: int = 100,
    top_n_clusters: int = 10,
) -> pd.DataFrame:
    """
    Detect pivot-based support/resistance zones and price-cluster congestion zones.
    Strength for both zone types is expressed as number of touches so they can be
    compared, filtered, and ranked on the same scale.

    Returns a DataFrame with columns:
        price, method, type, strength (touches), dist_pct
    sorted by price ascending.
    """
    if current_price is None:
        current_price = df["Close"].iloc[-1]

    # ── Pivot zones ────────────────────────────────────────────────────────────
    closes = df["Close"].values
    highs_idx = argrelextrema(closes, np.greater, order=order)[0]
    lows_idx  = argrelextrema(closes, np.less,    order=order)[0]

    raw_zones = []
    for i in highs_idx:
        raw_zones.append({"price": closes[i], "type": "resistance", "touches": 1, "idx": i})
    for i in lows_idx:
        raw_zones.append({"price": closes[i], "type": "support",    "touches": 1, "idx": i})

    raw_zones.sort(key=lambda z: z["price"])
    merged = []
    for z in raw_zones:
        if merged and abs(z["price"] - merged[-1]["price"]) / merged[-1]["price"] < zone_pct:
            last = merged[-1]
            last["price"]   = (last["price"] * last["touches"] + z["price"]) / (last["touches"] + 1)
            last["touches"] += 1
            last["type"]    = "both" if last["type"] != z["type"] else last["type"]
        else:
            merged.append(dict(z))

    pivot_zones = merged

    # ── Cluster zones — touches = pivot prices that fall inside each bin ───────
    all_prices = pd.concat([df["High"], df["Low"], df["Close"]])
    counts, edges = np.histogram(all_prices, bins=n_bins)
    peak_idx = argrelextrema(counts, np.greater, order=2)[0]

    pivot_prices = np.array([z["price"] for z in merged])  # pre-filter, all pivots

    cluster_zones = []
    for i in peak_idx:
        lo, hi   = edges[i], edges[i + 1]
        mid      = (lo + hi) / 2
        # touches = how many pivot prices landed inside this price bin
        touches  = int(np.sum((pivot_prices >= lo) & (pivot_prices <= hi)))
        cluster_zones.append({"price": mid, "touches": touches})

    cluster_zones.sort(key=lambda c: c["touches"], reverse=True)
    cluster_zones = cluster_zones[:top_n_clusters]

    # ── Build unified table ────────────────────────────────────────────────────
    rows = []
    for z in pivot_zones:
        rows.append({
            "price":    round(z["price"], 2),
            "method":   "pivot",
            "type":     z["type"],
            "strength": z["touches"],
        })
    for z in cluster_zones:
        rows.append({
            "price":    round(z["price"], 2),
            "method":   "cluster",
            "type":     "congestion",
            "strength": z["touches"],
        })

    if not rows:
        return pd.DataFrame(columns=["price", "method", "type", "strength", "dist_pct"])

    df_zones = pd.DataFrame(rows)
    df_zones["dist_pct"] = ((df_zones["price"] - current_price) / current_price * 100).round(2)
    df_zones.sort_values("price", inplace=True)
    df_zones.reset_index(drop=True, inplace=True)
    return df_zones


def build_price_action_patterns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # If talib is not available, return zeros for all patterns
    if not HAS_TALIB:
        for pattern_name in _ALL_PATTERN_COLS:
            out[pattern_name] = 0
        return out

    o = out["Open"].to_numpy().astype(float)
    h = out["High"].to_numpy().astype(float)
    l = out["Low"].to_numpy().astype(float)
    c = out["Close"].to_numpy().astype(float)
    norm = lambda raw: np.sign(raw).astype(int)

    out["PAT_DOJI"]              = norm(talib.CDLDOJI(o, h, l, c))
    out["PAT_DRAGONFLY_DOJI"]    = norm(talib.CDLDRAGONFLYDOJI(o, h, l, c))
    out["PAT_GRAVESTONE_DOJI"]   = norm(talib.CDLGRAVESTONEDOJI(o, h, l, c))
    out["PAT_HAMMER"]            = norm(talib.CDLHAMMER(o, h, l, c))
    out["PAT_HANGING_MAN"]       = norm(talib.CDLHANGINGMAN(o, h, l, c))
    out["PAT_INV_HAMMER"]        = norm(talib.CDLINVERTEDHAMMER(o, h, l, c))
    out["PAT_SHOOTING_STAR"]     = norm(talib.CDLSHOOTINGSTAR(o, h, l, c))
    out["PAT_MARUBOZU"]          = norm(talib.CDLMARUBOZU(o, h, l, c))
    out["PAT_SPINNING_TOP"]      = norm(talib.CDLSPINNINGTOP(o, h, l, c))
    out["PAT_MORNING_STAR"]      = norm(talib.CDLMORNINGSTAR(o, h, l, c))
    out["PAT_EVENING_STAR"]      = norm(talib.CDLEVENINGSTAR(o, h, l, c))
    out["PAT_MORNING_DOJI_STAR"] = norm(talib.CDLMORNINGDOJISTAR(o, h, l, c))
    out["PAT_EVENING_DOJI_STAR"] = norm(talib.CDLEVENINGDOJISTAR(o, h, l, c))
    out["PAT_ABANDONED_BABY"]    = norm(talib.CDLABANDONEDBABY(o, h, l, c))
    out["PAT_3_WHITE_SOLDIERS"]  = norm(talib.CDL3WHITESOLDIERS(o, h, l, c))
    out["PAT_3_BLACK_CROWS"]     = norm(talib.CDL3BLACKCROWS(o, h, l, c))
    out["PAT_3_INSIDE_UP_DOWN"]  = norm(talib.CDL3INSIDE(o, h, l, c))
    out["PAT_3_OUTSIDE_UP_DOWN"] = norm(talib.CDL3OUTSIDE(o, h, l, c))
    out["PAT_3_LINE_STRIKE"]     = norm(talib.CDL3LINESTRIKE(o, h, l, c))

    cols_to_drop = [
        c for c in _ALL_PATTERN_COLS
        if c in out.columns and _PAT_WEIGHT.get(c, 0) < MIN_WEIGHT_TO_SHOW
    ]
    out.drop(columns=cols_to_drop, inplace=True)
    return out


def _best_pattern(fired: List[str], min_weight: int = MIN_WEIGHT_TO_SHOW) -> Optional[str]:
    eligible = [c for c in fired if _PAT_WEIGHT.get(c, 0) >= min_weight]
    if not eligible:
        return None
    return max(eligible, key=lambda c: _PAT_WEIGHT.get(c, 0))


def _collect_zone_patterns(
    df: pd.DataFrame,
    pivot_zones: List[Dict],
    proximity: float = const.SR_PATTERN_ZONE_PROXIMITY,
    min_weight: int  = MIN_WEIGHT_TO_SHOW,
    min_gap: int     = MIN_BAR_GAP,
) -> List[Dict]:
    pat_cols  = [c for c in _ALL_PATTERN_COLS if c in df.columns]
    zone_data = [(z["price"], z["type"]) for z in pivot_zones
                 if z["type"] not in ("both", "congestion")]

    candidates: List[Dict] = []

    for bar_idx, row in df.iterrows():
        close = row["Close"]

        near = [(abs(close - zp) / zp, zt) for zp, zt in zone_data
                if abs(close - zp) / zp <= proximity]
        if not near:
            continue
        nearest_zone_type = min(near, key=lambda t: t[0])[1]

        fired_bull = [c for c in pat_cols
                      if c in BULLISH_PATTERNS
                      and row[c] == 1
                      and _PAT_WEIGHT.get(c, 0) >= min_weight]
        fired_bear = [c for c in pat_cols
                      if c in BEARISH_PATTERNS
                      and row[c] == -1
                      and _PAT_WEIGHT.get(c, 0) >= min_weight]

        best_bull = _best_pattern(fired_bull, min_weight)
        best_bear = _best_pattern(fired_bear, min_weight)

        if not best_bull and not best_bear:
            continue

        if best_bull and best_bear:
            wb = _PAT_WEIGHT.get(best_bull, 0)
            wr = _PAT_WEIGHT.get(best_bear, 0)
            if wb == wr:
                if nearest_zone_type == "support":
                    best_bear = None
                else:
                    best_bull = None
            elif wb > wr:
                best_bear = None
            else:
                best_bull = None

        winner = best_bull or best_bear
        if not winner:
            continue

        signal = 1 if winner == best_bull else -1
        candidates.append({
            "bar_idx": bar_idx,
            "high":    row["High"],
            "low":     row["Low"],
            "signal":  signal,
            "label":   _PAT_LABELS.get(winner, winner),
            "weight":  _PAT_WEIGHT.get(winner, 0),
        })

    candidates.sort(key=lambda c: c["weight"], reverse=True)
    kept: List[Dict] = []
    for cand in candidates:
        too_close = any(abs(cand["bar_idx"] - k["bar_idx"]) < min_gap for k in kept)
        if not too_close:
            kept.append(cand)

    kept.sort(key=lambda c: c["bar_idx"])
    return kept


class SwingSRStrategy(Strategy):
    atr_multiplier    = const.ATR_STOP_MULTIPLIER
    risk_reward_ratio = const.RISK_REWARD_RATIO
    risk_per_trade    = const.RISK_PER_TRADE
    zone_threshold    = const.ZONE_THRESHOLD

    def init(self):
        super().init()
        df = self.data.df.copy()

        raw_zones = identify_zones(df)

        # Filter: discard zones that haven't been touched enough times
        self.zone_table = raw_zones.reset_index(drop=True)

        self._pivot_zones = self.zone_table[
            self.zone_table["method"] == "pivot"
        ].to_dict("records")

        self._df  = build_price_action_patterns(df)
        self.atr  = self.I(lambda: self._df["volatility_atr"].values, name="ATR")

        self._risk = RiskManager(
            atr_multiplier=self.atr_multiplier,
            risk_reward_ratio=self.risk_reward_ratio,
            risk_per_trade=self.risk_per_trade,
        )

        self._active_bull_cols = [
            c for c in BULLISH_PATTERNS
            if c in self._df.columns and _PAT_WEIGHT.get(c, 0) >= MIN_WEIGHT_TO_SHOW
        ]
        self._active_bear_cols = [
            c for c in BEARISH_PATTERNS
            if c in self._df.columns and _PAT_WEIGHT.get(c, 0) >= MIN_WEIGHT_TO_SHOW
        ]

        self._last_trade_bar = -MIN_BAR_GAP

        # print(f"Active bullish cols ({len(self._active_bull_cols)}): {self._active_bull_cols}")
        # print(f"Active bearish cols ({len(self._active_bear_cols)}): {self._active_bear_cols}")

    def next(self):
        if self.position:
            return

        current_bar = len(self.data) - 1
        if current_bar - self._last_trade_bar < MIN_BAR_GAP:
            return

        price, atr = self.data.Close[-1], self.atr[-1]
        if pd.isna(atr) or atr == 0:
            return

        # Mirror _collect_zone_patterns: proximity filter against pivot zones only
        zone_data = [
            (z["price"], z["type"]) for z in self._pivot_zones
            if z["type"] not in ("both", "congestion")
        ]
        near = [
            (abs(price - zp) / zp, zt) for zp, zt in zone_data
            if abs(price - zp) / zp <= const.SR_PATTERN_ZONE_PROXIMITY
        ]
        if not near:
            return
        nearest_zone_type = min(near, key=lambda t: t[0])[1]

        row = self._df.iloc[current_bar]

        fired_bull = [
            c for c in self._active_bull_cols
            if int(row[c]) == 1
        ]
        fired_bear = [
            c for c in self._active_bear_cols
            if int(row[c]) == -1
        ]

        best_bull = _best_pattern(fired_bull)
        best_bear = _best_pattern(fired_bear)

        if not best_bull and not best_bear:
            return

        # Resolve tie exactly as _collect_zone_patterns does
        if best_bull and best_bear:
            wb, wr = _PAT_WEIGHT.get(best_bull, 0), _PAT_WEIGHT.get(best_bear, 0)
            if wb >= wr:
                best_bear = None
            else:
                best_bull = None

        if best_bull and nearest_zone_type == "support":
            order = self._risk.evaluate(self.equity, price, atr, "long")
            if order:
                self.buy(size=order["size"], sl=order["sl"], tp=order["tp"])
                self._last_trade_bar = current_bar

        elif best_bear and nearest_zone_type == "resistance":
            order = self._risk.evaluate(self.equity, price, atr, "short")
            if order:
                self.sell(size=order["size"], sl=order["sl"], tp=order["tp"])
                self._last_trade_bar = current_bar

    # ── plot ──────────────────────────────────────────────────────────────────

    def plot(self, save_path: str | None = None) -> str:
        """Plot candlestick chart with S/R zones and de-cluttered pattern annotations."""
        if not HAS_MATPLOTLIB:
            print("matplotlib not installed - plotting disabled")
            return ""
        if save_path is None:
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "sr_zones_chart.png")

        df = self._df.copy().reset_index(drop=True)
        x  = np.arange(len(df))

        BG, GRID = "#0d1117", "#1c2333"
        plt.rcParams.update({
            "figure.facecolor": BG, "axes.facecolor": BG,
            "axes.edgecolor": GRID, "axes.labelcolor": "#8b949e",
            "text.color": "#8b949e", "xtick.color": "#8b949e",
            "ytick.color": "#8b949e", "grid.color": GRID,
            "grid.linewidth": 0.6, "font.family": "monospace", "font.size": 8,
        })

        fig, (ax_p, ax_v, ax_a) = plt.subplots(
            3, 1, figsize=(16, 10), sharex=True,
            gridspec_kw={"height_ratios": [5, 1.4, 1.4], "hspace": 0.06},
        )

        BAND = 0.001
        for z in self._pivot_zones:
            if z["type"] in ("both", "congestion"):
                continue
            col, fa, ea = _ZONE_COLS[z["type"]]
            p = z["price"]
            ax_p.axhspan(p * (1 - BAND), p * (1 + BAND), color=col, alpha=fa, linewidth=0, zorder=1)
            ax_p.axhline(p, color=col, alpha=ea, linewidth=0.8, linestyle="--", zorder=2)
            ax_p.text(x[-1] + 0.8, p, f" {z['type'].upper()[:3]} {p:,.0f} ×{z['strength']}",
                      va="center", fontsize=7, color=col, alpha=0.85, clip_on=False)

        cp = df["Close"].iloc[-1]
        ax_p.axhline(cp, color="#ffffff", alpha=0.25, linewidth=0.8, linestyle=":", zorder=3)
        ax_p.text(x[-1] + 0.8, cp, f" NOW {cp:,.0f}", va="center",
                  fontsize=7.5, color="#ffffff", alpha=0.55, fontweight="bold", clip_on=False)

        UP, DN = "#2ecc71", "#e74c3c"
        for i, row in df.iterrows():
            up  = row["Close"] >= row["Open"]
            col = UP if up else DN
            ax_p.plot([i, i], [row["Low"], row["High"]], color=col, linewidth=0.8, zorder=4)
            ax_p.add_patch(Rectangle(
                (i - 0.3, min(row["Open"], row["Close"])),
                0.6, abs(row["Close"] - row["Open"]),
                facecolor=col, edgecolor=col, linewidth=0.4, zorder=5, alpha=0.95,
            ))

        price_range  = df["High"].max() - df["Low"].min()
        arrow_offset = price_range * 0.028

        annotations = _collect_zone_patterns(
            df, self._pivot_zones,
            proximity=const.SR_PATTERN_ZONE_PROXIMITY,
            min_weight=MIN_WEIGHT_TO_SHOW,
            min_gap=MIN_BAR_GAP,
        )

        for ann in annotations:
            i      = ann["bar_idx"]
            signal = ann["signal"]
            label  = ann["label"]

            if signal == 1:
                tip_y, tail_y = ann["low"], ann["low"] - arrow_offset
                txt_y  = tail_y - arrow_offset * 0.2
                col, va, a_style = "#2ecc71", "top", "->"
            else:
                tip_y, tail_y = ann["high"], ann["high"] + arrow_offset
                txt_y  = tail_y + arrow_offset * 0.2
                col, va, a_style = "#e74c3c", "bottom", "<-"

            ax_p.annotate(
                "",
                xy=(i, tip_y), xytext=(i, tail_y),
                arrowprops=dict(arrowstyle=a_style, color=col, lw=1.5, mutation_scale=11),
                zorder=8,
            )
            ax_p.text(
                i, txt_y, label,
                ha="center", va=va, fontsize=6.5, color=col, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                          edgecolor=col, alpha=0.85, linewidth=0.8),
                zorder=9, clip_on=True,
            )

        vc = ["#1a6640" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#6b1f1f"
              for i in range(len(df))]
        ax_v.bar(x, df["Volume"], width=0.7, color=vc, alpha=0.85, zorder=3)
        ax_v.set_ylabel("Volume", fontsize=7)
        ax_v.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v/1e3:.0f}K" if v < 1e6 else f"{v/1e6:.1f}M"))

        atr_col  = "#f5a623"
        atr_vals = df.get("volatility_atr", df.get("ATR", pd.Series(dtype=float)))
        ax_a.plot(x, atr_vals, color=atr_col, linewidth=1.2, zorder=3)
        ax_a.fill_between(x, atr_vals, alpha=0.15, color=atr_col)
        ax_a.set_ylabel("ATR(14)", fontsize=7)

        step     = max(1, len(df) // 12)
        tick_lbl = self._df.index[::step].strftime("%d-%b %H:%M").tolist()
        ax_a.set_xticks(x[::step])
        ax_a.set_xticklabels(tick_lbl, rotation=30, ha="right", fontsize=7)

        for ax in (ax_p, ax_v, ax_a):
            ax.grid(True, linestyle="--", zorder=0)
            ax.set_xlim(x[0] - 0.5, x[-1] + 14)

        ax_p.set_ylabel("Price", fontsize=8)
        ax_p.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
        ax_p.legend(handles=[
            mpatches.Patch(color="#2ecc71", alpha=0.6, label="Support"),
            mpatches.Patch(color="#e74c3c", alpha=0.6, label="Resistance"),
            mpatches.Patch(color="#ccff33", alpha=0.9, label="↑ Bullish pattern @ zone"),
            mpatches.Patch(color="#fb6107", alpha=0.9, label="↓ Bearish pattern @ zone"),
        ], loc="upper left", fontsize=7.5, framealpha=0.25, edgecolor=GRID, ncol=4)

        n_ann = len(annotations)
        fig.suptitle(
            f"S/R Zone Map  ·  Candlestick + Volume + ATR"
            f"  ·  {n_ann} key pattern(s) near S/R zones  [min_weight≥{MIN_WEIGHT_TO_SHOW}, gap≥{MIN_BAR_GAP}]",
            fontsize=11, fontweight="bold", color="#c8d4e8", y=0.998,
        )

        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
        plt.close(fig)
        print(f"✅  Saved → {save_path}  ({n_ann} annotations)")
        return save_path

    # ── internals ─────────────────────────────────────────────────────────────

    def _bullish_pattern_fired(self) -> bool:
        last = len(self._df) - 1
        return any(int(self._df[col].iloc[last]) == 1 for col in self._active_bull_cols)

    def _bearish_pattern_fired(self) -> bool:
        last = len(self._df) - 1
        return any(int(self._df[col].iloc[last]) == -1 for col in self._active_bear_cols)

    def _nearest_zone(self, price: float) -> Optional[Dict]:
        """
        Find the nearest zone within zone_threshold.
        Among equally-close zones, prefer the one with more touches (higher strength).
        """
        if self.zone_table.empty:
            return None
        df = self.zone_table.copy()
        df["dist"] = (df["price"] - price).abs() / price
        df = df[df["dist"] <= self.zone_threshold]
        if df.empty:
            return None
        # Primary: closest distance. Tiebreak: most touches (strength desc).
        return df.sort_values(
            ["dist", "strength"], ascending=[True, False]
        ).iloc[0].to_dict()