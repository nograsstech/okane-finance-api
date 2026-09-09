# ORB Strategy — Version A: Breakout Without Retest

**Strategy type:** 5-minute Opening Range Breakout  
**Entry style:** Immediate breakout entry, no retest required  
**Sessions:** London (08:00 GMT+1) · New York (09:30 EST)

---

## 1. Session Setup

| Session | Opening Range Window | Active Trading Window | Primary Instruments |
|---|---|---|---|
| London | 08:00–08:05 (GMT+1) | 08:05–11:00 | EUR/USD, GBP/USD, EUR/GBP, GBP/JPY |
| New York | 09:30–09:35 (EST) | 09:35–12:00 | EUR/USD, GBP/USD, USD/JPY, NAS100, SPX500 |

---

## 2. Opening Range Detection

1. At session open, wait for the **first 5-minute candle to fully close**.
2. Mark the **high of that candle** → this is your **OR High**.
3. Mark the **low of that candle** → this is your **OR Low**.
4. Draw horizontal lines at both levels. These are your breakout thresholds.
5. Calculate the **OR size in pips** (OR High − OR Low).

### Skip the session if:
- OR size exceeds the pair's typical session range (rough thresholds below)
- A major news event (NFP, CPI, FOMC, BOE/ECB rate decision) is scheduled within the active window
- OR High and OR Low are within **5 pips of each other** (range too tight)
- Price opened at a major weekly high/low or inside a multi-day consolidation zone

**Maximum OR size thresholds (skip if exceeded):**

| Instrument | London | New York |
|---|---|---|
| EUR/USD | 40 pips | 35 pips |
| GBP/USD | 50 pips | 45 pips |
| USD/JPY | 45 pips | 40 pips |
| NAS100 | — | 80 pts |

---

## 3. Entry Criteria

### Long entry
- A 5-minute candle **closes above OR High**
- Enter at the **open of the next candle** immediately following that breakout close

### Short entry
- A 5-minute candle **closes below OR Low**
- Enter at the **open of the next candle** immediately following that breakout close

### Entry filter — skip if:
- By the time the breakout candle closes, price has already moved more than **50% of the OR size** away from the breakout level (do not chase)
- The breakout candle has a wick that is longer than its body in the breakout direction (weak close, indecision)
- It is past the cutoff time for the active window (11:00 London / 12:00 New York)

---

## 4. Stop Loss

| Direction | Stop Placement |
|---|---|
| Long | Below OR Low — or below the breakout candle's low if structure supports a tighter placement |
| Short | Above OR High — or above the breakout candle's high if structure supports it |

**Minimum stop = full OR range in pips.** Do not use a stop tighter than the OR size on this version. Without retest confirmation, the wider stop is necessary to avoid being stopped out on normal pullback noise.

---

## 5. Take Profit Targets

All targets are measured from the **entry price**, not from the OR level.

| Target | Distance from Entry | Action |
|---|---|---|
| TP1 | 1× OR size | Close 50% of position |
| TP2 | 2× OR size | Close remaining 50%, or trail |
| TP3 | 3× OR size | Optional runner — only if a major S/R level aligns |

**After TP1 is hit:** Move stop to breakeven on the remaining position.  
**After TP2 is hit (if running to TP3):** Trail stop to TP1 level.

---

## 6. Trade Management Rules

- **Risk per trade:** 0.5–1% of account
- **Max trades per session:** 1 (this strategy only)
- **No re-entry:** If stop is hit, do not re-enter on the same session's OR
- **No opposite trade:** If long is stopped out, do not flip short on the same OR — the range is likely broken and the setup is invalidated
- **One direction only per session:** If the long triggers first, ignore any subsequent short signal

---

## 7. Risk/Reward Profile

| Metric | Expected Value |
|---|---|
| Typical R:R | 1:1 to 1:3 |
| Win rate (indicative) | 40–55% |
| Edge source | Session momentum continuation; institutional order flow at open |

> **Note:** Lower win rate than Version B is expected. The edge comes from the size of winners versus losers when the move is genuine. Proper risk management and discipline on skipping setups is what makes this version profitable over a sample of trades.

---

## 8. Checklist (pre-trade)

- [ ] First 5-minute candle has closed — OR High and Low marked
- [ ] OR size is within the instrument's threshold — not too wide
- [ ] No major news event in the active window
- [ ] Price has not already moved >50% of OR size from the level at breakout close
- [ ] Risk is sized to 0.5–1% of account based on stop distance
- [ ] Entry time is within the active trading window
- [ ] No prior trade has been taken this session on this strategy

---

## 9. Worked Example (London session, EUR/USD long)

1. London opens at 08:00. First candle: High = 1.08420, Low = 1.08360 → **OR = 6 pips**
2. OR size (6 pips) is within threshold. No news. Setup is valid.
3. At 08:10, a 5-minute candle closes at 1.08435 — above OR High (1.08420). Breakout confirmed.
4. Price at close is 1.08435, which is 1.5 pips above OR High — within the 50% threshold (3 pips max). Enter at open of next candle.
5. **Entry:** 1.08440
6. **Stop:** 1.08360 (OR Low) → 8 pips
7. **TP1:** 1.08440 + 6 pips = 1.08500 → close 50%
8. **TP2:** 1.08440 + 12 pips = 1.08560 → close remainder
9. **After TP1:** Move stop to 1.08440 (breakeven)

---

*Last updated: 2026 · Strategy version: A (no retest)*
