# Repository guidance

Read `README.md` for setup, architecture, endpoint, strategy-extension, quality, and Docker
commands. Treat `pyproject.toml`, `.python-version`, and the current code as authoritative when
documentation and configuration disagree.

## Working constraints

- Use Python 3.13 and uv. `pyproject.toml` plus `uv.lock` are the only dependency sources.
- Preserve endpoint paths and methods, HTTP Basic requirements, environment-variable names,
  response field names, database schema, public strategy identifiers, calculations, and
  deployment behavior unless the task explicitly changes one.
- Keep core HTTP flow as router → focused service → repository. Add a layer only when it removes
  a concrete duplication or gives an independently testable boundary.
- Keep numerical strategy, HMM, and portfolio-replay code cohesive. File length alone is not a
  reason to split an algorithm.
- Avoid live yfinance, database, notification, or cron calls in tests. Mock external boundaries.
- Preserve unrelated legacy modules and their existing style when a task targets the core.

## Core boundaries

- `app/main.py` creates the FastAPI application and registers routers.
- `app/config.py` owns lazy typed settings. Importing application modules must not open network
  clients or prompt for credentials.
- `app/signals/router.py` owns HTTP validation and authentication.
- `app/signals/services/` owns signal, backtest, replay, result-rendering, and scheduled-job
  orchestration.
- `app/signals/service.py` is a compatibility facade for existing imports; put new behavior in
  the focused service module.
- `app/db/repository.py` owns PostgreSQL queries. Services should not issue SQL directly.
- `app/base/utils/mongodb.py` owns the lazy process-wide Motor client.
- `app/signals/utils/yfinance.py` owns Yahoo Finance access. Explicit `start` and `end` values
  take precedence; period-based fetching remains the fallback.

Blocking yfinance, strategy, backtesting.py, and HTML-rendering work runs off the event loop.
Backtest HTML must use a unique temporary path and remain zlib-compressed plus base64-encoded on
the wire and in persistence. Scheduled strategy refreshes isolate each strategy failure so one
bad strategy does not stop the remaining jobs.

## Strategy identifiers

Python package names must be valid identifiers. Public IDs are API contracts and can differ from
package names:

- `five_min_orb` → `5_min_orb`
- `five_min_orb_confirmation` → `5_min_orb_confirmation`

Add a strategy through direct imports and dispatch in `app/signals/strategies/calculate.py` and
`app/signals/strategies/perform_backtest.py`, then register its public ID in
`app/signals/strategies/strategy_list.py`. Add characterization and numerical tests with it.

## Verification

Run the non-integration suite and focused coverage command from `README.md`. Run `uv run mypy` and
the focused Ruff path list in `.github/workflows/ci.yml`. The selected core has an 80% coverage
gate; whole-application coverage and legacy Ruff debt are separate follow-up work.

Integration tests require real services and must remain marked `integration`. Unit tests use
in-memory SQLite or mocked repositories and `mongomock-motor` where applicable.

The vendored `pandas-ta` wheel supports the repository's NumPy/Python combination. Keep its
`pyproject.toml` source mapping unless a dependency task explicitly replaces and verifies it.
