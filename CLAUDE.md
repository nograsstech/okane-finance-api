# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Package Management (uv)
```zsh
# Install all dependencies (uses .python-version which specifies 3.13+)
uv sync

# Install with dev dependencies (pytest, ruff, mypy, etc.)
uv sync --dev

# Add a runtime dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>

# Sync to lock file exactly (for reproducible builds)
uv sync --frozen
```

**Important:** The `pandas-ta` dependency is a local vendor wheel (`vendor/pandas_ta-0.3.14b0-py3-none-any.whl`). Do not remove this from `pyproject.toml`.

### Running the Application
```zsh
# Development server with auto-reload
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Alternative (FastAPI CLI)
fastapi dev app.main:app

# Production server (via Docker)
docker build -t okane-finance-api .
docker run -p 8000:8000 --env-file .env okane-finance-api
```

### Testing
```zsh
# Run all tests
pytest

# Run single test file
pytest tests/test_postgres_repository.py

# Run with coverage
pytest --cov=app

# Skip integration tests (unit tests use in-memory SQLite and mongomock)
pytest -m "not integration"
```

### Code Quality
```zsh
# Linting
ruff check app/ tests/

# Format code
black app/ tests/

# Type checking
mypy app/
```

### Docker Deployment
```zsh
# Build for Google Cloud Run
./build-push-deploy.sh

# Or manually:
docker build -t okane-finance-api .
docker run -p 8000:8000 --env-file .env okane-finance-api
```

## Architecture Overview

This is a **microservices-oriented FastAPI application** for financial signals, AI analysis, and trading strategy backtesting.

### Core Architecture Pattern
- **Router → Service → Repository** layered architecture
- **Fully async** (async/await throughout) using SQLAlchemy 2.0+ with psycopg3 for Postgres
- **Motor** for async MongoDB operations
- **Repository pattern** for database abstraction (prevents direct DB access from services)

### Key Services

| Service | Router | Responsibility |
|---------|--------|----------------|
| `signals/` | `router.py` | Technical indicators, trading signals, backtesting |
| `ai/` | `router.py` | Chatbot (LangGraph + Google Gemini), sentiment analysis |
| `news/` | `router.py` | News fetching, sentiment scoring |
| `ticker/` | `router.py` | Ticker data, historical prices (yfinance) |
| `notification/` | `router.py` | Discord/LINE webhooks, push notifications |

### Database Layer

**PostgreSQL (Supabase)**
- **Models:** `app/db/models.py` — SQLAlchemy ORM models (`BacktestStat`, `TradeAction`, `UniqueStrategy`)
- **Session:** `app/db/postgres.py` — Async session factory with psycopg3
- **Repository:** `app/db/repository.py` — Data access layer (BacktestStatRepository, TradeActionRepository, UniqueStrategyRepository)
- **Connection String:** Read from `DATABASE_URL` env var. Automatically normalizes `postgres://` URLs to `postgresql+psycopg://`
- **Important:** Uses `channel_binding=disable` and `prepare_threshold=0` for Supabase pgBouncer compatibility

**MongoDB**
- **Client:** `app/base/utils/mongodb.py` — Module-level Motor singleton (AsyncIOMotorClient)
- **Collections:** `stock_lists`, `news`, `news_with_sentiment`, `price_histories`, `ticker_infos`
- **Database:** Switches between `production` and `develop` based on `ENV` env var

### Trading Strategy System

Located in `app/signals/strategies/`:

```
strategies/
├── strategy_list.py              # Master list of enabled strategies
├── calculate.py                  # Signal calculation orchestration
├── perform_backtest.py           # Backtest execution using backtesting.py
└── <strategy_name>/
    ├── <strategy_name>.py        # Strategy class (inherits from backtesting.Strategy)
    └── <strategy_name>_backtest.py # Backtest configuration
```

**Available Strategies** (from `strategy_list.py`):
1. **ema_bollinger** - EMA + Bollinger Bands crossover
2. **ema_bollinger_1_low_risk** - Lower risk EMA Bollinger variant
3. **macd_1** - MACD-based signals
4. **clf_bollinger_rsi** - Classifier with Bollinger + RSI (15m interval)
5. **clf_bollinger_rsi_15m** - 15-minute version
6. **eurjpy_bollinger_rsi_60m** - EUR/JPY specific, 60-minute
7. **grid_trading** - Grid trading strategy
8. **super_safe_strategy** - Conservative approach
9. **fvg_confirmation** - Fair Value Gap confirmation

**To add a new strategy:**
1. Create a new directory under `strategies/`
2. Implement the strategy class inheriting from `backtesting.Strategy`
3. Add to `strategy_list.py`
4. Create corresponding backtest configuration

**Signal Generation:** `app/signals/signals_generator/` contains individual signal generators (EMA, MACD, RSI, etc.)

### AI/Chatbot System

- **Framework:** LangGraph for conversation flow management
- **LLM:** Google Gemini (via `langchain-google-genai`)
- **Memory:** In-memory store (thread-scoped conversations)
- **Tools:** `app/ai/tools/` — YFinance news, sentiment analysis, DuckDuckGo search
- **UI:** Chainlit mounted at `/chat` for interactive web interface

### Notification System

Two notification paths:
1. **Direct webhooks** (Discord/LINE) via `notification/service.py`
2. **Discord Bot** at `app/bots/discord_bot.py` for interactive commands

## Environment Variables

Required in `.env`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (Supabase) |
| `MONGO_USER`, `MONGO_PASSWORD` | MongoDB Atlas credentials |
| `GOOGLE_API_KEY` | Google Gemini LLM access |
| `ALPHA_VANTAGE_API_KEY` | Alternative data source |
| `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID` | Discord bot integration |
| `DISCORD_WEBHOOK_URL` | Discord push notifications |
| `LINE_SECRET` | LINE messaging |
| `OKANE_FINANCE_API_USER`, `OKANE_FINANCE_API_PASSWORD` | HTTP Basic auth |
| `SUPABASE_URL`, `SUPABASE_KEY` | Supabase client |
| `ENV` | `development` or `production` (switches MongoDB DB name) |

## Important Implementation Notes

### Async/Await Conventions
- All DB operations use `async with AsyncSessionLocal() as session:`
- CPU-bound work (backtesting, data fetching) is offloaded to threads via `asyncio.to_thread()`
- Never mix sync and async DB calls in the same request path

### Vendor Dependency
- `pandas-ta` is a patched vendored wheel for NumPy 2.x compatibility
- File: `vendor/pandas_ta-0.3.14b0-py3-none-any.whl`
- Do not replace with PyPI version without testing NumPy 2.x compatibility

### Supabase/pgBouncer Gotchas
- `asyncpg` driver has SCRAM-SHA-256-PLUS incompatibility → use `psycopg[async]` instead
- Transaction pooler (port 6543) requires `prepare_threshold=0`
- Channel binding must be disabled: `channel_binding=disable`

### Testing Strategy
- Unit tests use in-memory SQLite (`sqlite+aiosqlite://`) — no Postgres required
- MongoDB tests use `mongomock-motor` — no MongoDB required
- Integration tests marked with `@pytest.mark.integration` require real DATABASE_URL
- Fixtures in `tests/conftest.py`

### CORS Configuration
Frontend is deployed to Vercel. CORS origins in `app/main.py` include:
- `https://okane-signals.vercel.app`
- Wildcards for preview deployments: `https://*okane-signals*.vercel.app`
- Local: `http://localhost:5173`, `http://localhost:4173`

## API Endpoints Reference

All endpoints require **HTTP Basic Authentication** (via `get_current_username` dependency).

### Root
- `GET /` - Health check, returns `{"status": 200, "message": "Monii 0.1.0"}`

### Signals (`/signals`)
- `GET /signals` - Get trading signals for a ticker/strategy
- `GET /signals/backtest` - Queue async backtest (returns UUID)
- `GET /signals/backtest/sync` - Run backtest synchronously
- `POST /signals/strategy-notification-job` - Trigger strategy notification job

### AI (`/ai`)
- `GET /ai/graph` - Get LangGraph visualization (PNG)
- `POST /ai/chatbot-with-tool` - Stream chatbot responses (SSE)
- `GET /ai/chat?thread_id=xxx` - Get chat history

### News (`/news`)
- News sentiment and feed endpoints

### Ticker (`/ticker`)
- Ticker data and historical price endpoints

### Notification (`/notification`)
- Webhook and notification management

### Chainlit Chat UI
- `/chat` - Mounted Chainlit interface

## Tech Stack Reference

### Core
- **Python 3.13+** (uses uv for dependency management)
- **FastAPI** - High-performance async web framework
- **Pydantic v2** - Data validation and settings management
- **Uvicorn** - ASGI server

### Data & Financial
- **yfinance** - Yahoo Finance data
- **pandas-ta** - Technical analysis (vendor wheel patched for numpy 2.x)
- **backtesting.py** - Strategy backtesting
- **pandas/numpy** - Data processing

### AI/LLM
- **LangChain/LangGraph** - AI framework and conversation management
- **Google Generative AI (Gemini)** - LLM for chatbot
- **OpenAI SDK** - Additional AI capabilities
- **Anthropic SDK** - Alternative AI provider

### Database
- **PostgreSQL (via Supabase)** - Primary database for backtest stats and trade actions
- **MongoDB (motor)** - Async MongoDB for flexible schema data
- **SQLAlchemy 2.x** - ORM with async support via psycopg[async]

### Observability
- **OpenTelemetry** - Distributed tracing
- **Traceloop SDK** - LLM observability
- **PostHog** - Analytics
- **Loguru** - Structured logging

### Deployment
- **Docker** - 2-stage production builds
- **docker-compose** - Local orchestration
- **GitHub Actions** - VPS deployment pipeline

## Database Schema Reference

### PostgreSQL (Supabase)

#### `backtest_stats`
Core table storing backtest results:
- Identifiers: `ticker`, `strategy`, `period`, `interval`, `ref_id`
- Performance metrics: `return_percentage`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`
- Drawdown stats: `max_drawdown_percentage`, `max_drawdown_duration`
- Trade stats: `trade_count`, `win_rate`, `profit_factor`, `exposure_time_percentage`
- Strategy params: `tpsl_ratio`, `sl_coef`, `tp_coef`
- HTML: `html` (deflated + base64 encoded backtest plot)
- Timestamps: `updated_at`, `last_optimized_at`

#### `trade_actions`
Individual trades from backtests:
- Foreign key: `backtest_id` → `backtest_stats.id`
- Trade details: `datetime`, `trade_action`, `entry_price`, `price`, `sl`, `tp`, `size`

#### `unique_strategies`
View/table of active strategy configurations with notifications enabled

### MongoDB
Collections: `stock_lists`, `news`, `news_with_sentiment`, `price_histories`, `ticker_infos`

## Troubleshooting

### MongoDB Connection Issues
Check `MONGO_USER` and `MONGO_PASSWORD` in `.env`. Verify network connectivity.

### pandas-ta Import Errors
Ensure vendor wheel is present: `vendor/pandas_ta-0.3.14b0-py3-none-any.whl`
Run `uv sync` to reinstall.

### Backtest HTML Not Displaying
HTML is deflated + base64 encoded. Use decompression utilities in `app/lib/utils/pako.py`.

### Discord Bot Not Responding
Verify `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID`. Check bot has necessary permissions.

## Memory Bank

Additional project documentation is stored in `memory-bank/`:
- `projectbrief.md` - Project goals and requirements
- `techContext.md` - Technology choices and constraints
- `systemPatterns.md` - Architecture and design patterns
- `productContext.md` - Vision and user stories
- `progress.md` - Development progress tracking
- `activeContext.md` - Current work context
