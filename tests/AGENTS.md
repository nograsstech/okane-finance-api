# Tests

- No live yfinance, database, notification, or cron calls. Mock external
  boundaries: `monkeypatch.setattr` on module attributes, in-memory SQLite,
  `mongomock-motor` for Mongo.
- Tests requiring real services carry the `integration` mark; the default suite
  runs `-m "not integration"`.
- Contract tests (`test_openapi_contract.py`, `test_signals_api_contracts.py`)
  pin route shapes and DTO fields — update them deliberately when a contract
  changes, never to make a failure pass.
- `test_backtest_worker_safety.py` enforces worker-safety invariants by
  reflection over dispatcher exports; a new `*_backtest` that drops
  `skip_optimization` fails it.
- Core coverage gate: `app.signals.services`, `utils/yfinance`, `hmm_service`,
  `portfolio_replay`, `auth.basic_auth` at 80% (see README for the command).
