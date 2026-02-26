"""
Constants for the swing-1 support/resistance pattern strategy.
"""

# ── Strategy Parameters ────────────────────────────────────────────────────────
ATR_STOP_MULTIPLIER = 2.0          # ATR multiplier for stop-loss distance
RISK_REWARD_RATIO = 2.0            # Risk-to-reward ratio (TP/SL)
RISK_PER_TRADE = 0.02              # Risk 2% of equity per trade
ZONE_THRESHOLD = 0.03              # Zone proximity threshold (3%)

# ── Support/Resistance Detection ────────────────────────────────────────────────
SR_ZONE_THRESHOLD = 0.015          # Zone merge threshold (1.5%)
SR_PATTERN_ZONE_PROXIMITY = 0.02   # Max distance for pattern-zone matching (2%)
MIN_BAR_GAP = 5                    # Minimum bars between trades

# ── Pattern Definitions ─────────────────────────────────────────────────────────
# Bullish candlestick patterns
BULLISH_PATTERNS = [
    "PAT_DOJI",
    "PAT_DRAGONFLY_DOJI",
    "PAT_HAMMER",
    "PAT_INV_HAMMER",
    "PAT_MARUBOZU",
    "PAT_SPINNING_TOP",
    "PAT_MORNING_STAR",
    "PAT_MORNING_DOJI_STAR",
    "PAT_ABANDONED_BABY",
    "PAT_3_WHITE_SOLDIERS",
    "PAT_3_INSIDE_UP_DOWN",
    "PAT_3_OUTSIDE_UP_DOWN",
    "PAT_3_LINE_STRIKE",
]

# Bearish candlestick patterns
BEARISH_PATTERNS = [
    "PAT_DOJI",
    "PAT_GRAVESTONE_DOJI",
    "PAT_HANGING_MAN",
    "PAT_SHOOTING_STAR",
    "PAT_MARUBOZU",
    "PAT_SPINNING_TOP",
    "PAT_EVENING_STAR",
    "PAT_EVENING_DOJI_STAR",
    "PAT_ABANDONED_BABY",
    "PAT_3_BLACK_CROWS",
    "PAT_3_INSIDE_UP_DOWN",
    "PAT_3_OUTSIDE_UP_DOWN",
    "PAT_3_LINE_STRIKE",
]

# ── Pattern Metadata ─────────────────────────────────────────────────────────────
# Pattern labels for display
_PAT_LABELS = {
    "PAT_DOJI": "Doji",
    "PAT_DRAGONFLY_DOJI": "Dragonfly Doji",
    "PAT_GRAVESTONE_DOJI": "Gravestone Doji",
    "PAT_HAMMER": "Hammer",
    "PAT_HANGING_MAN": "Hanging Man",
    "PAT_INV_HAMMER": "Inverted Hammer",
    "PAT_SHOOTING_STAR": "Shooting Star",
    "PAT_MARUBOZU": "Marubozu",
    "PAT_SPINNING_TOP": "Spinning Top",
    "PAT_MORNING_STAR": "Morning Star",
    "PAT_EVENING_STAR": "Evening Star",
    "PAT_MORNING_DOJI_STAR": "Morning Doji Star",
    "PAT_EVENING_DOJI_STAR": "Evening Doji Star",
    "PAT_ABANDONED_BABY": "Abandoned Baby",
    "PAT_3_WHITE_SOLDIERS": "3 White Soldiers",
    "PAT_3_BLACK_CROWS": "3 Black Crows",
    "PAT_3_INSIDE_UP_DOWN": "3 Inside",
    "PAT_3_OUTSIDE_UP_DOWN": "3 Outside",
    "PAT_3_LINE_STRIKE": "3 Line Strike",
}

# Pattern reliability weights (higher = more significant)
_PAT_WEIGHT = {
    "PAT_DOJI": 3,
    "PAT_DRAGONFLY_DOJI": 4,
    "PAT_GRAVESTONE_DOJI": 4,
    "PAT_HAMMER": 5,
    "PAT_HANGING_MAN": 5,
    "PAT_INV_HAMMER": 4,
    "PAT_SHOOTING_STAR": 5,
    "PAT_MARUBOZU": 6,
    "PAT_SPINNING_TOP": 2,
    "PAT_MORNING_STAR": 6,
    "PAT_EVENING_STAR": 6,
    "PAT_MORNING_DOJI_STAR": 7,
    "PAT_EVENING_DOJI_STAR": 7,
    "PAT_ABANDONED_BABY": 8,
    "PAT_3_WHITE_SOLDIERS": 7,
    "PAT_3_BLACK_CROWS": 7,
    "PAT_3_INSIDE_UP_DOWN": 4,
    "PAT_3_OUTSIDE_UP_DOWN": 5,
    "PAT_3_LINE_STRIKE": 5,
}

# ── Visualization Colors ─────────────────────────────────────────────────────────
# Zone colors for plotting (color, fill_alpha, edge_alpha)
_ZONE_COLS = {
    "support": ("#2ecc71", 0.25, 0.6),      # Green
    "resistance": ("#e74c3c", 0.25, 0.6),   # Red
}

# All pattern columns for filtering
_ALL_PATTERN_COLS = [
    "PAT_DOJI",
    "PAT_DRAGONFLY_DOJI",
    "PAT_GRAVESTONE_DOJI",
    "PAT_HAMMER",
    "PAT_HANGING_MAN",
    "PAT_INV_HAMMER",
    "PAT_SHOOTING_STAR",
    "PAT_MARUBOZU",
    "PAT_SPINNING_TOP",
    "PAT_MORNING_STAR",
    "PAT_EVENING_STAR",
    "PAT_MORNING_DOJI_STAR",
    "PAT_EVENING_DOJI_STAR",
    "PAT_ABANDONED_BABY",
    "PAT_3_WHITE_SOLDIERS",
    "PAT_3_BLACK_CROWS",
    "PAT_3_INSIDE_UP_DOWN",
    "PAT_3_OUTSIDE_UP_DOWN",
    "PAT_3_LINE_STRIKE",
]
