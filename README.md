# okane-finance-api

Okane Finance API — signals, AI, and financial data platform built with FastAPI.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.14+ | [python.org](https://www.python.org/) or `pyenv install 3.14` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

## Local Development

Quickly start the dev server
```zsh
uv sync
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 1. Create & activate the virtual environment

```zsh
# uv reads .python-version (3.14) and creates .venv automatically
uv sync
source .venv/bin/activate
```

### 2. Install dependencies (including dev tools)

```zsh
uv sync --dev
```

> **Note:** The `pandas_ta` dependency is a local vendor wheel (`vendor/pandas_ta-0.3.14b0-py3-none-any.whl`). uv resolves it automatically via `pyproject.toml`.

### 3. Run the development server

```zsh
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at: `http://127.0.0.1:8000`

---

## Package Management

This project uses **[uv](https://github.com/astral-sh/uv)** for fast, reproducible dependency management.

```zsh
# Add a new runtime dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>

# Remove a dependency
uv remove <package>

# Sync environment to match lock file exactly
uv sync --frozen
```

The `uv.lock` file is **committed to the repository** to guarantee reproducible builds across environments and CI.

---

## Typing & Validation

This project uses **[Pydantic v2](https://docs.pydantic.dev/)** as its primary data validation and typing library. All request/response schemas and config models are defined with Pydantic.

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SignalResponse(BaseModel):
    symbol: str
    action: str
    confidence: float
```

---

## Docker

### Build

```zsh
docker build -t okane-finance-api .
```

The Dockerfile uses a **2-stage build**:
1. **Builder** — installs all dependencies with uv into a `.venv`
2. **Runtime** — copies the `.venv` into a lean image, runs as a non-root `appuser`

### Run

```zsh
docker run -p 8000:8000 --env-file .env okane-finance-api
```

### Health check

```zsh
curl http://localhost:8000/
```

---

## Project Structure

```
okane-finance-api/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── signals/         # Trading signal logic
│   ├── ai/              # AI/LLM integrations
│   ├── news/            # News feed endpoints
│   ├── ticker/          # Ticker data endpoints
│   ├── notification/    # Push notification service
│   ├── auth/            # Authentication
│   ├── db/              # SQLAlchemy database models & repositories
│   └── base/            # Shared models & interfaces
├── tests/               # Pytest suite
├── public/              # Static files
├── vendor/              # Local wheel packages (pandas_ta)
├── pyproject.toml       # ← single source of truth for deps
├── uv.lock              # ← committed lock file
├── .python-version      # ← pins Python 3.14
└── Dockerfile           # ← 2-stage production build
```

---

## Trading Strategies

This platform implements multiple algorithmic trading strategies for forex and other instruments. Strategies are located in `app/signals/strategies/`.

### Available Strategies

| Strategy | Description | Timeframe | Instruments |
|----------|-------------|-----------|-------------|
| `ema_bollinger` | EMA + Bollinger Bands crossover | Multiple | Forex, Stocks |
| `macd_1` | MACD-based signals | Multiple | Forex, Stocks |
| `clf_bollinger_rsi` | Classifier with Bollinger + RSI | 15m | Forex |
| `grid_trading` | Grid trading strategy | Multiple | Forex |
| `super_safe_strategy` | Conservative approach | Multiple | Forex |
| `fvg_confirmation` | Fair Value Gap confirmation | Multiple | Forex |

---

## 5-Minute ORB Strategies

Two session-based opening range breakout strategies for London and New York trading sessions.

### Version A (`5_min_orb`)

**Entry Style:** Immediate breakout entry (no retest required)

**Trading Rules:**
- Identify Opening Range: First 5-minute candle after session open
- Long Entry: Candle closes above OR High → Enter next candle open
- Short Entry: Candle closes below OR Low → Enter next candle open
- Entry Filters:
  - Don't chase if price moved >50% of OR size from breakout level
  - Skip if breakout candle has wick > body (weak close)
  - No entries after cutoff time (11:00 London / 12:00 NY)

**Stop Loss:** Below OR Low (long) / Above OR High (short) + spread buffer

**Take Profit:**
- TP1 = 1× OR size (close 50%)
- TP2 = 2× OR size (close remaining 50%)
- Optional TP3 = 3× OR size (only if major S/R level aligns)

**Sessions:**
- London: 08:00-11:00 local time
- New York: 09:30-12:00 local time

**Instruments:** EUR/USD, GBP/USD, USD/JPY, EUR/GBP, GBP/JPY

**Expected Performance:**
- Win Rate: 40-55%
- Trade Frequency: Higher (catches all breakouts)
- Edge: Size of winners vs losers when move is genuine

### Version B (`5_min_orb_confirmation`)

**Entry Style:** Breakout with retest confirmation required

**Three-Step Process:**
1. Detect initial breakout (no entry yet)
2. Wait for retest to OR level (within 2-3 pips)
3. Enter on confirmation (candle close or rejection wick)

**Confirmation Options:**
- Option A: Candle touches OR level and closes back in breakout direction
- Option B: Rejection wick at OR level (wick ≥ 2× body)

**Stop Loss:** 3-5 pips from OR level (tighter, using OR as support/resistance)

**Take Profit:**
- TP1 = 1.5× OR size (close 50%)
- TP2 = 2.5-3× OR size (close remaining 50%)

**Missed Setups:** 30-40% of breakouts won't retest (by design)

**Expected Performance:**
- Win Rate: 55-65%
- Trade Frequency: Lower (waits for retest)
- Edge: Higher win rate from structural confirmation

### Usage

```python
from app.signals.strategies.calculate import calculate_signals
from app.signals.strategies.five_min_orb.five_min_orb_backtest import backtest as orb_a_backtest

# Generate signals
params = {'ticker': 'EUR/USD', 'session': 'london'}
df_signals = five_min_orb_signals(df, params)

# Run backtest
bt, stats, trades, strategy_params = orb_a_backtest(df_signals, params, size=0.03, skip_optimization=True)
```

### Risk Management

- Risk per trade: 0.5-1% of account
- Max trades per session: 1 (no re-entry)
- No opposite trades after stop hit (setup invalidated)

---