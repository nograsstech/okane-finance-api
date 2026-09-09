# okane-finance-api

FastAPI backend-for-frontend for Okane Finance. It serves trading signals and market-regime
data, runs strategy backtests and replays, persists results, and exposes a scheduled strategy
notification job. The repository also contains the existing AI, news, ticker, notification,
and Chainlit features.

## Requirements

- Python 3.13 (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Docker, only when building or running the container

`pyproject.toml` and `uv.lock` are the dependency sources of truth. The patched `pandas-ta`
wheel in `vendor/` is resolved through `pyproject.toml`.

## Local development

Install the locked runtime and development dependencies:

```zsh
uv sync --frozen --dev
```

Configure the required environment variables in `.env`, then start the API:

```zsh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API is available at `http://127.0.0.1:8000`; FastAPI documentation is at `/docs`.
Core settings are loaded lazily, so importing `app.main` does not connect to a database or
prompt for credentials.

Core environment variables retain their existing names:

| Variable | Purpose |
| --- | --- |
| `OKANE_FINANCE_API_USER` | HTTP Basic username |
| `OKANE_FINANCE_API_PASSWORD` | HTTP Basic password |
| `DATABASE_URL` | PostgreSQL connection string |
| `MONGO_USER` | MongoDB username |
| `MONGO_PASSWORD` | MongoDB password |
| `ENV` | Selects the `production` or `develop` MongoDB database |

AI, notification, and deployment modules require their existing provider-specific variables.

## Core structure

```text
app/
├── main.py                         # Application factory and router registration
├── config.py                       # Lazy typed settings
├── auth/basic_auth.py              # HTTP Basic dependency
├── db/
│   ├── postgres.py                 # Lazy async SQLAlchemy setup
│   └── repository.py               # PostgreSQL persistence operations
├── base/utils/mongodb.py           # Lazy shared Motor client
└── signals/
    ├── router.py                   # Stable HTTP endpoints
    ├── dto.py                      # Signal, backtest, and replay wire schemas
    ├── service.py                  # Compatibility imports for existing callers
    ├── services/
    │   ├── signals.py              # Signal request orchestration
    │   ├── backtests.py            # Backtest execution, persistence, notifications
    │   ├── replay.py               # Stored-trade replay
    │   ├── results.py              # Shared stats, HTML, and compression helpers
    │   └── strategy_jobs.py        # Strategy listing and scheduled refresh job
    ├── portfolio_replay.py         # Cohesive portfolio replay calculation
    ├── hmm_service.py              # Cohesive HMM regime calculation
    ├── utils/yfinance.py           # Market-data adapter
    └── strategies/                 # Strategy algorithms and dispatch
```

Routers own HTTP validation and authentication. Services orchestrate market-data calls,
offload blocking calculations, and coordinate repositories. Numerical HMM, portfolio replay,
and strategy algorithms remain cohesive instead of being split by file length.

## Core endpoints

All `/signals` endpoints use HTTP Basic authentication.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/signals/` | Generate signals |
| `GET` | `/signals/backtest` | Queue a background backtest and return its UUID |
| `GET` | `/signals/backtest/sync` | Run a backtest and return the full result envelope |
| `GET` | `/signals/backtest/replay` | Replay one stored backtest |
| `POST` | `/signals/portfolio-replay` | Replay enabled strategies as a portfolio |
| `POST` | `/signals/strategy-notification-job` | Run the scheduled strategy refresh |
| `GET` | `/signals/strategies` | List public strategy identifiers |
| `GET` | `/signals/hmm/regimes` | Calculate market-regime probabilities |

Successful structured responses retain the `{status, message, data}` envelope.

## Tests and quality checks

Run the non-integration suite:

```zsh
uv run pytest -m "not integration" --tb=short -q
```

Run the focused core coverage gate:

```zsh
uv run pytest -m "not integration" --tb=short -q \
  --cov=app.signals.services \
  --cov=app.signals.utils.yfinance \
  --cov=app.signals.hmm_service \
  --cov=app.signals.portfolio_replay \
  --cov=app.auth.basic_auth \
  --cov=app.base.utils.mongodb \
  --cov=app.db.repository \
  --cov-report=term-missing \
  --cov-fail-under=80
```

Run the configured focused type check:

```zsh
uv run mypy
```

CI also runs Ruff against the refactored core and its tests; its explicit path list avoids a
repository-wide formatting diff in legacy modules. Whole-application coverage and legacy Ruff
debt are tracked separately and are not hidden with broad ignore rules.

## Adding a strategy

1. Create a valid Python package under `app/signals/strategies/`.
2. Implement the signal calculation and backtest entry point using the existing neighboring
   strategies as the smallest useful template.
3. Add direct imports and dispatch cases in `strategies/calculate.py` and
   `strategies/perform_backtest.py`.
4. Add the public identifier to `strategies/strategy_list.py`.
5. Add tests for signal calculation, dispatch, and the expected numerical behavior.

Python package names and public strategy identifiers are separate. For example,
`five_min_orb` is the internal package while `5_min_orb` remains the public API identifier;
`five_min_orb_confirmation` similarly maps to `5_min_orb_confirmation`.

Full contracts (function signatures, the four-value backtest return, worker-safety
rules, verification commands): `docs/adding-a-strategy.md`.

## Utility scripts

Repository utilities live under `scripts/`. For example, the stock-list refresh reads MongoDB
credentials from the normal environment settings:

```zsh
uv run python scripts/refresh_us_stock_marketcap.py
```

This script performs network and database writes; do not use it as a test command.

## Docker

Build and run the production image:

```zsh
docker build -t okane-finance-api .
docker run --rm -p 8000:8000 --env-file .env okane-finance-api
```

The multi-stage image installs from `pyproject.toml` and `uv.lock` with Python 3.13 and runs
the application as a non-root user.

### Health check

```zsh
curl http://localhost:8000/health
```

Backtest requests skip parameter optimization by default. Pass
`skip_optimization=false` only for deliberate, resource-intensive optimization runs.
