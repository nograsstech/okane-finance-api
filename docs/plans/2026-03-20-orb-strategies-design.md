# ORB Strategies Design Document

**Date:** 2026-03-20
**Author:** Claude Code
**Status:** Approved

## Overview

Implementation of two 5-minute Opening Range Breakout (ORB) strategies for the Okane Finance API:

1. **Version A** (`5_min_orb`): Immediate breakout entry, no retest required
2. **Version B** (`5_min_orb_confirmation`): Breakout with retest confirmation required

Both strategies target London (08:00 GMT+1) and New York (09:30 EST) session opens, with configurable parameters for optimization per instrument and session.

---

## Architecture

### Directory Structure

```
app/signals/strategies/
├── 5_min_orb/
│   ├── __init__.py
│   ├── 5_min_orb_signals.py          # TotalSignal generation (Version A)
│   ├── 5_min_orb_backtest.py         # Strategy class & backtest (Version A)
│   └── orb_utils.py                  # Shared utilities (timezone, session detection)
├── 5_min_orb_confirmation/
│   ├── __init__.py
│   ├── 5_min_orb_confirmation_signals.py  # TotalSignal generation (Version B)
│   └── 5_min_orb_confirmation_backtest.py # Strategy class & backtest (Version B)
```

### Strategy Registration

Updates required in:
- `app/signals/strategies/strategy_list.py` — Add strategy names
- `app/signals/strategies/calculate.py` — Add routing logic

---

## Core Components

### 1. Session Detection & Timezone Handling

**Challenge:** ORB is session-based, not continuous. Data arrives in UTC from yfinance.

**Solution:**
```python
# Utilities in orb_utils.py:
- convert_utc_to_session_time(utc_timestamp, session) -> local_time
- detect_session_window(candle_time, session) -> bool
- is_session_open(candle_time, session) -> bool
- get_session_cutoff_time(session) -> timestamp
```

**DST Handling:**
- London: GMT+0 (winter) / GMT+1 (summer) — last Sunday March to October
- New York: EST (GMT-5) / EDT (GMT-4) — second Sunday March to November
- Use `pytz` or `zoneinfo` for accurate timezone conversion

**Session Windows:**
| Session | Open Time | Active Window | Cutoff Time |
|---------|-----------|---------------|-------------|
| London  | 08:00 local | 08:05-11:00 | 11:00 |
| New York| 09:30 local | 09:35-12:00 | 12:00 |

### 2. Opening Range Detection

```python
# For each session:
1. Find first 5-min candle that closes after session open time
2. Mark OR_High = candle.High, OR_Low = candle.Low
3. Calculate OR_size_pips = (OR_High - OR_Low) / pip_value
4. Apply filters:
   - Skip if OR_size_pips > threshold (per instrument)
   - Skip if OR_size_pips < 5 pips (too tight)
   - Skip if major news scheduled (future enhancement)
5. Track OR levels throughout session
```

**OR Size Thresholds (configurable):**
| Instrument | London | New York |
|------------|--------|----------|
| EUR/USD    | 40 pips| 35 pips  |
| GBP/USD    | 50 pips| 45 pips  |
| USD/JPY    | 45 pips| 40 pips  |

### 3. Signal Generation - Version A (Immediate Entry)

**State Machine:**
```
WAITING_OR → OR_FORMED → BREAKOUT_SIGNAL → ACTIVE_TRADE
```

**Entry Criteria:**
- 5-min candle closes above OR_High (long) or below OR_Low (short)
- Enter at open of **next candle**

**Entry Filters (skip if any true):**
- Price moved >50% of OR size from breakout level
- Breakout candle wick > body (weak close)
- Past cutoff time (11:00 London / 12:00 NY)
- Already in a trade this session

**TotalSignal Values:**
- `0` = No signal (outside window, OR not formed, waiting)
- `1` = Sell signal (short entry)
- `2` = Buy signal (long entry)

### 4. Signal Generation - Version B (Retest Confirmation)

**State Machine:**
```
WAITING_OR → OR_FORMED → BREAKOUT_DETECTED → WAITING_RETEST → CONFIRMATION → ACTIVE_TRADE
```

**Three-Step Process:**

**Step 1 — Initial Breakout (Observation Only)**
- Candle closes above/below OR level
- Set state = BREAKOUT_DETECTED
- **Do NOT enter yet**

**Step 2 — Retest of OR Level**
- Price must return to OR level (within 2-3 pips tolerance)
- Timeout: 6 candles (30 minutes) after breakout
- If no retest → Skip session

**Step 3 — Confirmation (Entry Trigger)**

**Option A — Candle Close:**
- Candle touches OR level and closes back in breakout direction
- Enter at open of **next candle**

**Option B — Rejection Wick:**
- Rejection wick at OR level (wick ≥ 2× body)
- Enter at **close of rejection candle**

**Void Conditions:**
- Price closes back inside OR (level failed)
- No retest within 30 minutes
- Past cutoff time

### 5. Configurable Parameters

```python
# Per-instrument, per-session optimization:
{
    "eurusd_london": {
        "or_size_threshold": 40,        # max pips
        "chase_threshold": 0.5,         # max move as % of OR size
        "min_or_size": 5,               # min pips
        "tp1_multiplier": 1.0,          # TP1 as % of OR size
        "tp2_multiplier": 2.0,          # TP2 as % of OR size
        "sl_atr_multiplier": 1.5,       # SL as % of ATR
        "entry_timeout_bars": 6,        # max bars for retest (Version B)
        "retest_tolerance_pips": 3,     # tolerance for OR retest
        "spread_buffer_pips": 2         # buffer for spread in SL
    },
    "gbpusd_ny": { ... },
    # ... similar for other instruments/sessions
}
```

---

## Backtest Implementation

### Strategy Classes

Both strategies inherit from `backtesting.Strategy` following existing patterns.

**Common Features:**
- ATR-based position sizing (0.5-1% risk per trade)
- Trade logging (`trades_actions` list)
- One trade per session (no re-entry)
- Positions held until SL/TP hit (no time-based exit)

**Version A: FiveMinORBStrat**
```python
class FiveMinORBStrat(Strategy):
    mysize = 0.03
    or_size_pips = 0

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)

    def next(self):
        # Entry: immediate on breakout
        if self.signal1 == 2 and len(self.trades) == 0:
            # Long: SL below OR Low
            sl = self.data.OR_Low[-1] - self.spread_buffer
            tp1 = self.data.Close[-1] + (self.or_size_pips * self.pip_value)
            self.buy(sl=sl, tp=tp1, size=self.mysize * 0.5)

        # Trade management
        # - Move SL to breakeven after TP1
        # - Trail stop if running to TP3
```

**Version B: FiveMinORBConfirmationStrat**
```python
class FiveMinORBConfirmationStrat(Strategy):
    # Similar structure but:
    # - Tighter SL (3-5 pips from OR level)
    # - Higher TP multipliers (1.5×, 2.5-3×)
    # - Immediate exit if price closes through OR level
```

**Stop Loss Placement:**
| Version | Direction | Stop Placement |
|---------|-----------|----------------|
| A       | Long      | Below OR Low + spread buffer |
| A       | Short     | Above OR High + spread buffer |
| B       | Long      | 3-5 pips below OR High (now support) |
| B       | Short     | 3-5 pips above OR Low (now resistance) |

**Take Profit Targets (from entry price):**
| Version | TP1              | TP2              | TP3 (optional) |
|---------|------------------|------------------|----------------|
| A       | 1× OR size       | 2× OR size       | 3× OR size     |
| B       | 1.5× OR size     | 2.5-3× OR size   | —              |

**Trade Management Rules:**
- After TP1: Move stop to breakeven on remaining position
- After TP2 (Version A): Trail stop to TP1 level if holding for TP3
- After TP2 (Version B): Trail stop by 1× OR size below/above swing low/high
- Version B: Immediate exit if price closes through OR level after entry

---

## Data Columns

### Added to DataFrame during signal generation:

**Opening Range Columns:**
- `OR_High` — Opening range high price
- `OR_Low` — Opening range low price
- `OR_Size_Pips` — OR size in pips
- `OR_Session` — Session label ('london', 'ny', or None)
- `OR_Formed` — Boolean, True if OR detected for this session
- `Breakout_Detected` — Boolean, Version B only

**Signal Columns:**
- `TotalSignal` — 0=None, 1=Sell, 2=Buy

**Utility Columns:**
- `Local_Time` — Candle time in session timezone
- `Is_Session_Window` — Boolean, True if in active trading window
- `Pip_Value` — Pip value for instrument (0.0001 or 0.01)

---

## Error Handling & Edge Cases

1. **No session candles** → Return DataFrame with all TotalSignal = 0
2. **Weekend/holiday data** → Skip sessions with insufficient candles
3. **Early session end** → Close any signals at data boundary
4. **Instrument pip values** → Auto-detect (JPY pairs = 0.01, others = 0.0001)
5. **Spread handling** → Add configurable buffer to SL
6. **Partial candles** → Ignore incomplete candles at session boundaries
7. **Multiple sessions** → Track state separately for London and NY
8. **NaN indicators** → Drop rows with essential NaN values before backtest
9. **Empty DataFrame** → Return early with warning

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_orb_utils.py`
```python
- test_convert_utc_to_london_summer()
- test_convert_utc_to_london_winter()
- test_convert_utc_to_ny_edt()
- test_convert_utc_to_ny_est()
- test_detect_session_window_london()
- test_detect_session_window_ny()
- test_calculate_or_size_eurusd()
- test_calculate_or_size_usdjpy()
- test_detect_breakout_long()
- test_detect_breakout_short()
```

**File:** `tests/test_orb_signals.py`
```python
- test_version_a_signal_generation()
- test_version_b_signal_generation()
- test_version_a_skip_chase()
- test_version_b_retest_timeout()
- test_or_size_threshold_skip()
- test_multiple_sessions_in_dataset()
```

### Integration Tests

**File:** `tests/test_orb_backtest.py`
```python
- test_backtest_execution_version_a()
- test_backtest_execution_version_b()
- test_trade_action_logging()
- test_sl_tp_placement()
- test_one_trade_per_session()
- test_parameter_optimization()
```

### Manual Validation

1. Run backtests on historical data (2023-2025)
2. Verify signal count matches manual chart analysis
3. Check SL/TP levels are correct
4. Confirm win rate matches expected range (A: 40-55%, B: 55-65%)

---

## Performance Optimization

### Considerations:
1. **Vectorized operations** where possible (pandas/numpy)
2. **Session filtering** — Only process candles in active windows
3. **Early termination** — Skip sessions once cutoff time passed
4. **Caching** — Cache timezone conversions, OR calculations

### Backtest Optimization:
- Use `skip_optimization=True` for production (pre-optimized parameters)
- Use `skip_optimization=False` for parameter discovery
- Limit optimization grid search to sensible ranges

---

## Future Enhancements

1. **News filtering** — Skip sessions with major economic events (NFP, CPI, FOMC)
2. **Multi-timeframe confirmation** — Add higher timeframe trend filter
3. **Volatility filter** — Skip sessions with extreme ATR
4. **Session performance tracking** — Track win rate per session/instrument
5. **Dynamic OR size** — Adjust thresholds based on recent volatility
6. **Partial TP** — Close 25% at TP1, 25% at TP2, hold remainder
7. **Trailing stop optimization** — Test different trailing methods

---

## Success Criteria

### Functional Requirements:
- ✅ Both strategies generate correct signals for London and NY sessions
- ✅ DST transitions handled correctly
- ✅ OR size thresholds enforced per instrument
- ✅ Version B three-step process works correctly
- ✅ Backtests execute without errors
- ✅ Trade actions logged correctly

### Performance Goals:
- Win rate within expected range (A: 40-55%, B: 55-65%)
- Profit factor > 1.5 after optimization
- Max drawdown < 25%
- Sharpe ratio > 1.0

### Code Quality:
- Follows existing codebase patterns
- Passes all tests (unit + integration)
- Documentation complete
- No performance regressions

---

## References

- **Version A Strategy:** `app/signals/strategies/5_min_orb/orb-strategy-version-a.md`
- **Version B Strategy:** `app/signals/strategies/5_min_orb_confirmation/orb-strategy-version-b.md`
- **Existing Strategy Pattern:** `app/signals/strategies/ema_bollinger/`
- **Backtesting Framework:** `backtesting.py` library

---

## Appendix: Instrument Configuration

### Supported Instruments & Pip Values

| Ticker | Type    | Pip Value | London Sessions | NY Sessions |
|--------|---------|-----------|-----------------|-------------|
| EUR/USD| Forex   | 0.0001    | ✅              | ✅          |
| GBP/USD| Forex   | 0.0001    | ✅              | ✅          |
| USD/JPY| Forex   | 0.01      | ❌              | ✅          |
| EUR/GBP| Forex   | 0.0001    | ✅              | ❌          |
| GBP/JPY| Forex   | 0.01      | ✅              | ❌          |

### Default OR Size Thresholds

```python
OR_THRESHOLDS = {
    "EUR/USD": {"london": 40, "ny": 35},
    "GBP/USD": {"london": 50, "ny": 45},
    "USD/JPY": {"ny": 40},
    "EUR/GBP": {"london": 40},
    "GBP/JPY": {"london": 45},
}
```

### Session Time Windows (UTC, assuming winter time)

```python
SESSION_WINDOWS = {
    "london": {
        "open": "07:00",   # 08:00 GMT
        "active_start": "07:05",  # 08:05 GMT
        "active_end": "10:00",    # 11:00 GMT
        "timezone": "Europe/London"
    },
    "ny": {
        "open": "14:30",   # 09:30 EST
        "active_start": "14:35",  # 09:35 EST
        "active_end": "17:00",    # 12:00 EST
        "timezone": "America/New_York"
    }
}
```

*Note: These UTC times shift by 1 hour during DST. Always convert dynamically.*
