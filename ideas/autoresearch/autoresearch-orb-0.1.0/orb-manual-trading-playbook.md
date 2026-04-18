# Opening Range Breakout (ORB) Manual Trading Playbook

**Date:** 2026-04-18
**Based on:** 108 backtest experiments across 10 instruments (forex + commodities + indices)
**Best recorded mean Sharpe:** 1.6066 | **Mean max drawdown:** -0.92%

---

## Instruments

Trade these instruments only. Backtested across all; robustness requires diversification.

| Category | Symbols |
|----------|---------|
| Forex | EURUSD, GBPUSD, USDJPY, USDCAD, EURJPY |
| Commodities | GC (Gold), SI (Silver), CL (Crude Oil) |
| Indices | SPY, QQQ |

---

## Sessions

Two independent sessions per day. Each has its own opening range and trade count.

| Session | Times (UTC) | Times (Thailand, ICT +7) | Times (ET) | Times (London) |
|---------|-------------|--------------------------|------------|----------------|
| London | 08:00 - 12:30 | 15:00 - 19:30 | 03:00 - 07:30 | 08:00 - 12:30 |
| New York | 13:30 - 20:00 | 20:30 - 03:00+1 | 08:30 - 15:00 | 13:30 - 20:00 |

---

## Day Filter

**Trade Tuesday through Friday only. Skip Monday.**

Monday is consistently choppy across all instruments. Experiment `3c0b71c` proved skipping Monday improved Sharpe from 0.10 to 0.53.

---

## Step-by-Step Execution

### Step 1: Determine if Today Is a Trading Day

- Check day of week. If Monday: **no trades.**
- Check for major scheduled news (NFP, FOMC, CPI). Consider sitting out or reducing size.

### Step 2: Classify the Instrument (Narrow vs Wide Range)

This determines your directional rules and stop placement.

**At session open, note the current price.** After the range forms (Step 3), compute:

```
range_pct = (range_high - range_low) / midpoint_price
```

Where `midpoint_price = (range_high + range_low) / 2`

| Classification | Range % | Examples (typical) |
|---------------|---------|-------------------|
| **Narrow** | < 0.20% | Most forex pairs (EURUSD, GBPUSD, USDJPY, USDCAD, EURJPY) |
| **Wide** | >= 0.20% | Commodities (GC, SI, CL), sometimes indices (SPY, QQQ) |

### Step 3: Build the Opening Range (First 30 Minutes)

**Time:** First 6 bars (30 minutes) of each session.

| Session | Observation Period |
|---------|-------------------|
| London | 08:00 - 08:29 UTC |
| New York | 13:30 - 13:59 UTC |

**Rules during observation (DO NOT TRADE):**

1. Mark the **highest high** of these 6 bars = `range_high`
2. Mark the **lowest low** of these 6 bars = `range_low`
3. Compute `range_height = range_high - range_low`
4. Compute `midpoint = (range_high + range_low) / 2`
5. Compute `range_pct = range_height / midpoint`

**Minimum range filter:** If `range_pct < 0.03%`, skip this session. Range too thin to trade.

### Step 4: Wait for Confirmation (Skip 2 Bars After Range Forms)

**Critical rule — do not enter on the first or second bar after the range completes.**

After the 6-bar range forms, **skip bars 7 and 8** (10 minutes). Start watching for entries on bar 9.

**Rationale:** Experiment `3dec95e` showed skipping 2 bars post-range improved Sharpe from 1.60 to 1.61 by filtering false breakouts.

| Session | Range Done | Skip Window | Entry Window |
|---------|-----------|-------------|-------------|
| London | 08:30 UTC | 08:30 - 08:39 | 08:40 - 09:19 |
| New York | 14:00 UTC | 14:00 - 14:09 | 14:10 - 14:49 |

### Step 5: Determine Allowed Directions

This depends on the session AND whether the pair is narrow-range.

```
is_narrow = range_pct < 0.002  (i.e. < 0.20%)
is_london = session is London (08:00 UTC open)
is_ny     = session is New York (13:30 UTC open)
```

| Session | Narrow Pair | Wide Pair |
|---------|------------|-----------|
| London | **Longs ONLY** | Both directions |
| New York | **Shorts ONLY** | Both directions |

**Do NOT trade against the directional filter.** Experiment `f4114eb` proved London shorts were a drag. Experiment `f6b4d18` confirmed the narrow/wide split.

### Step 6: Identify Entry Signal

You have a **10-bar window** (50 minutes) from bar 9 to bar 18 of the session.

**Long trigger:**
```
close > range_high * (1 + 0.001)
```
i.e., price closes above `range_high + 0.1%`

**Short trigger:**
```
close < range_low * (1 - 0.001)
```
i.e., price closes below `range_low - 0.1%`

**Only take the trigger if it matches your allowed direction from Step 5.**

### Step 7: Place the Trade

**Entry:** Market order on the bar that triggers.

#### Stop Loss Placement

| Pair Type | Stop Loss | Formula |
|-----------|-----------|---------|
| **Narrow** (range_pct < 0.2%) | 2/3 into range | `long_sl = range_low + (2/3 * range_height)` |
| **Narrow** (range_pct < 0.2%) | 2/3 into range | `short_sl = range_high - (2/3 * range_height)` |
| **Wide** (range_pct >= 0.2%) | Beyond range boundary | `long_sl = range_low` |
| **Wide** (range_pct >= 0.2%) | Beyond range boundary | `short_sl = range_high` |

**Visual guide for narrow pairs:**
```
range_high ─────────── short_sl (wide) / short entry zone
   │  1/3  │  1/3  │  1/3  │
   │       │       │       │
range_low  ─────────── long_sl (wide) / long entry zone

For narrow: SL at the 2/3 mark (closer to midpoint)
For wide:  SL at the boundary (full range away)
```

#### Take Profit

```
TP = entry_price ± (range_height * 1.0)
```

- Long TP: `entry + range_height`
- Short TP: `entry - range_height`

**Do not deviate from 1.0x.** Experiments `4fb58e1`, `42e8743`, `dd51c40` all confirmed 1.0x is optimal.

### Step 8: Manage the Trade

- **1 trade per session per instrument.** After entering, stop looking for more signals in that session.
- Let the stop or target hit. No manual overrides.
- **No trailing stops.** Experiment `1052c1c` proved trailing stops are dead code — fixed SL/TP performs better.

### Step 9: Session End

- **Close all open positions at session end.** No overnight holds.
- London session: flatten everything by 12:30 UTC.
- NY session: flatten everything by 20:00 UTC.
- If stop/target hasn't hit by session close, close manually at market.

---

## Position Sizing

The backtest uses $100,000 notional with 2 bps ($0.0002) commission. For manual trading:

1. **Risk per trade:** 0.5% - 1.0% of account
2. **Calculate distance to stop:** `entry - stop_loss` for longs
3. **Position size:** `risk_amount / distance_to_stop`
4. **Max simultaneous positions:** Consider correlation — don't stack EURUSD + GBPUSD + USDJPY longs at the same time

---

## Quick Reference Card

```
TODAY'S CHECKLIST:
□ Not Monday
□ Session: London (08:00 UTC) or NY (13:30 UTC)
□ Build range: first 30 min (6 bars)
□ Skip 2 bars after range (10 min wait)
□ Compute range_pct → narrow (<0.2%) or wide (>=0.2%)
□ Direction filter:
    London + narrow → longs only
    NY + narrow → shorts only
    Either + wide → both directions
□ Entry: close breaks range ± 0.1%
□ SL: 2/3 into range (narrow) or boundary (wide)
□ TP: 1x range height from entry
□ 1 trade per session, then done
□ Close all at session end
```

---

## What NOT to Do (Lessons from Failed Experiments)

| Mistake | Experiment | Why It Fails |
|---------|-----------|-------------|
| Trade Mondays | `3c0b71c` vs baseline | Choppy, directional noise |
| Use 3-bar (15min) range | `456f654` | Too narrow, noisy S/R levels |
| Remove breakout threshold | `92eec9d` | Weak breakouts fail, 0.1% filter helps |
| 2+ trades per session | `6799cdb` | Over-trading, more losses |
| Wider TP (1.5x-2x) | `4fb58e1`, `42e8743` | Doesn't fill, bigger drawdown |
| Tighter TP (0.75x-0.8x) | `6714dcb`, `4aae789` | Cuts winners short |
| Tighter SL (0.75x range) | `11f4066` | Frequent stop-outs |
| Trade London shorts | `f4114eb` | London shorts were net drag |
| Use 4-bar range | `2b7a006` | Noisier levels |
| Hold overnight | `a062c1e` | Gap risk, forced close is better |
| Confirmation bar entry | `53c89de` | Enters at worse price |
| Volume confirmation | `3d67be7` | Kills all forex trades |
| Body-based range (Close) | `e28586d` | Wick H/L levels are better S/R |
| Use time exit (bar count) | `21814bf` | Closes winners prematurely |
| SMA trend filter | `67fdb7b` | Kills commodity trades |
| Breakout momentum filter | `2c05113` | Helps commodities, kills forex |

---

## Instrument-Specific Notes

### Forex Pairs (typically narrow range)
- EURUSD, GBPUSD: Most liquid, tightest spreads. Best for beginners.
- USDJPY, EURJPY: Can have wider ranges during risk-on/off moves.
- USDCAD: Correlated with oil — check CL when trading USDCAD.

### Commodities (typically wide range)
- GC (Gold): Best London session performer.
- SI (Silver): More volatile than gold, wider stops.
- CL (Crude Oil): Best in NY session. Check API/EIA inventory times.

### Indices
- SPY, QQQ: NY session only makes sense (London has low volume).
- QQQ can get 0 trades with strict filters — this is expected, not a bug.

---

## Daily Routine

### Pre-Market (Before 08:00 UTC)
- Check economic calendar for scheduled news
- Check overnight futures direction (bias for London session)
- Prepare chart templates with 5-minute bars

### London Session (08:00 - 12:30 UTC)
- 08:00-08:29: Watch and mark range high/low
- 08:30-08:39: Wait (skip 2 bars)
- 08:40-09:19: Watch for breakout in allowed direction
- 09:19-12:30: Manage open trade or wait (no new entries)
- 12:25-12:30: Close any open position

### Between Sessions (12:30 - 13:30 UTC)
- Log London results
- Check US pre-market data
- Reset for NY session

### New York Session (13:30 - 20:00 UTC)
- 13:30-13:59: Watch and mark range high/low
- 14:00-14:09: Wait (skip 2 bars)
- 14:10-14:49: Watch for breakout in allowed direction
- 14:49-20:00: Manage open trade or wait
- 19:55-20:00: Close any open position

### End of Day
- Log all trades
- Calculate daily P&L
- Review any deviations from the playbook

---

## Record Keeping Template

```
Date: ___________  Day: ___________
Session: London / NY  Instrument: ___________

Range High: ________  Range Low: ________
Range Height: ________  Range %: ________
Classification: Narrow / Wide

Direction Allowed: Long / Short / Both
Entry Time: ________  Entry Price: ________
Direction: Long / Short
Stop Loss: ________  Take Profit: ________

Exit Time: ________  Exit Price: ________
Exit Reason: TP Hit / SL Hit / Session End / Manual
P&L: ________

Notes: _________________________________________________
```

---

*Generated from autoresearch-orb backtest results. Past performance does not guarantee future results. This playbook is a starting point — adapt to your broker's execution, spreads, and your own risk tolerance.*
