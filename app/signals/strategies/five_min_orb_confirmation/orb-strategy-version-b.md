# ORB Strategy — Version B: Breakout With Retest Confirmation

**Strategy type:** 5-minute Opening Range Breakout  
**Entry style:** Breakout + retest confirmation required before entry  
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

## 3. Entry Criteria — Three-Step Process

Version B requires **three sequential events** before entering. Missing any one step means no trade.

### Step 1 — Initial breakout (observation only, not entry)

- A 5-minute candle closes **above OR High** (for a potential long) or **below OR Low** (for a potential short)
- **Do not enter yet.** This is only confirmation that a breakout has occurred.
- Note the breakout candle's close price. This will be used to assess retest depth.

### Step 2 — Retest of the OR level

- After the breakout, price must pull back and **return to the broken OR level**
- **For longs:** price pulls back down to OR High, which now acts as support
- **For shorts:** price pulls back up to OR Low, which now acts as resistance
- The retest does not need to be exact — a touch within **2–3 pips of the OR level** is acceptable

### Step 3 — Confirmation candle (entry trigger)

One of the following must occur at the retest level:

**Option A — Candle close confirmation:**
- A 5-minute candle touches the OR level during the retest and then **closes back in the breakout direction**
- Long: candle closes above OR High after touching it
- Short: candle closes below OR Low after touching it
- Enter at the open of the **next candle** after the confirmation close

**Option B — Rejection wick / pin bar:**
- The retest candle prints a clear rejection wick off the OR level (wick points into the OR, body stays on the breakout side)
- The wick should be at least 2× the body size
- Enter at the **close of the rejection candle** (do not wait for the next candle open)

### Void conditions — do not enter if:
- Price passes through the OR level and closes back inside the OR — the level has failed as support/resistance
- No retest occurs within the **active trading window** — the setup is void, do not chase
- The retest takes more than **6 candles (30 minutes)** to form — momentum has faded, skip
- It is past the cutoff time for the active window (11:00 London / 12:00 New York)

---

## 4. Stop Loss

Because the retest provides structural confirmation, a **tighter stop is appropriate**.

| Direction | Stop Placement |
|---|---|
| Long | 3–5 pips below OR High (the level now acts as support) |
| Short | 3–5 pips above OR Low (the level now acts as resistance) |

If price closes back through the OR level at any point after entry, **exit immediately** — the trade thesis is invalidated regardless of whether the stop has been hit.

---

## 5. Take Profit Targets

All targets are measured from the **entry price**.

| Target | Distance from Entry | Action |
|---|---|---|
| TP1 | 1.5× OR size | Close 50% of position |
| TP2 | 2.5–3× OR size | Close remaining 50%, or trail |

The tighter stop in Version B produces a better R:R than Version A at equivalent TP levels — TP1 at 1.5× and TP2 at 2.5–3× is achievable without extending targets.

**After TP1 is hit:** Move stop to breakeven on the remaining position.  
**After TP2 is hit (if still holding):** Trail stop by 1× OR size below/above the most recent swing low/high.

---

## 6. Trade Management Rules

- **Risk per trade:** 0.5–1% of account
- **Max trades per session:** 1 (this strategy only)
- **No re-entry after stop:** If stop is hit, do not re-enter on the same session's OR
- **Failed retest = immediate exit:** If the OR level breaks through after entry (price closes back inside the OR), exit at market — do not wait for the stop
- **One direction only per session:** If the long setup triggers first, ignore any subsequent short signal on the same OR

---

## 7. Missed Breakout Rule

Approximately 30–40% of genuine breakouts will not produce a clean retest. When that happens:

- **Do not chase.** If price never returns to the OR level, there is no setup.
- Do not switch to Version A mid-session — that defeats the purpose of a defined system.
- Accept the miss. The edge of this version comes from higher win rate on confirmed setups, not from catching every move.

---

## 8. Risk/Reward Profile

| Metric | Expected Value |
|---|---|
| Typical R:R | 1:1.5 to 1:4+ |
| Win rate (indicative) | 55–65% |
| Edge source | Structural confirmation at OR level; better entries reduce stop outs |

> **Note:** Higher win rate than Version A, but fewer total setups — you will miss a portion of valid breakouts that do not retest. The tradeoff is worthwhile when discipline is maintained consistently.

---

## 9. Checklist (pre-trade)

- [ ] First 5-minute candle has closed — OR High and Low marked
- [ ] OR size is within the instrument's threshold — not too wide
- [ ] No major news event in the active window
- [ ] Step 1 complete: initial breakout candle has closed above OR High or below OR Low
- [ ] Watching for retest — not entering yet
- [ ] Step 2 complete: price has returned to the OR level within 30 minutes of breakout
- [ ] Step 3 complete: confirmation candle (close or rejection wick) at the OR level
- [ ] Risk is sized to 0.5–1% of account based on tight stop distance
- [ ] Entry time is within the active trading window
- [ ] No prior trade has been taken this session on this strategy

---

## 10. Worked Example (New York session, EUR/USD long)

1. NY opens at 09:30. First candle: High = 1.08500, Low = 1.08440 → **OR = 6 pips**
2. OR size within threshold. No news. Setup is valid.
3. At 09:40, a candle closes at 1.08515 — above OR High. **Step 1 complete.** (No entry yet.)
4. At 09:50, price pulls back to 1.08502 — touching OR High from above. **Step 2 complete.**
5. The 09:50 candle closes at 1.08510 — a bullish close above OR High with a small wick below it. **Step 3 complete — Option A.**
6. **Entry:** Open of the 09:55 candle = 1.08511
7. **Stop:** 1.08500 − 4 pips = 1.08496 → ~1.5 pips below OR High (use 4 pips total stop for spread + buffer)
8. **TP1:** 1.08511 + 9 pips (1.5× OR) = 1.08600 → close 50%
9. **TP2:** 1.08511 + 18 pips (3× OR) = 1.08691 → close remainder
10. **After TP1:** Move stop to 1.08511 (breakeven)

---

## 11. Comparison with Version A

| | Version A (no retest) | Version B (retest) |
|---|---|---|
| Entry trigger | Breakout candle close | Retest + confirmation |
| Entry speed | Immediate | Delayed — requires pullback |
| Stop width | Full OR range | 3–5 pips (tight) |
| Win rate | 40–55% | 55–65% |
| R:R potential | 1:1 – 1:3 | 1:1.5 – 1:4+ |
| Missed setups | Few | 30–40% of breakouts won't retest |
| Best suited for | Traders watching screen at open | Traders who prioritize R:R and discipline |

---

*Last updated: 2026 · Strategy version: B (retest confirmation)*
