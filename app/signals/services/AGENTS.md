# Signal services

HTTP flow is router → one focused module here → repository. `app/signals/service.py`
is a compatibility facade only; every new behavior goes into the module that owns it:

- `backtests.py` — run, persist, notify. Executes backtests through `BACKTEST_EXECUTOR`
  with `asyncio.wait_for`; never `asyncio.to_thread` for the backtest call itself.
- `signals.py` — signal generation (yfinance → `calculate_signals` → DTO).
- `replay.py` — replay stored `TradeAction` rows against fresh prices.
- `results.py` — pure helpers: stats envelope, persistence payload, HTML rendering.
- `strategy_jobs.py` — strategy listing and the scheduled refresh; one failing
  strategy must not stop the others.

## Constraints

- No SQL here; `app/db/repository.py` owns queries.
- Blocking work (yfinance, strategy math, HTML render) goes off the event loop.
- Backtest HTML uses a unique temporary path and stays zlib+base64 on the wire
  and in persistence.
- Keep functions importable without network clients or credentials
  (`app/config.py` settings are lazy).

## Tests

`tests/test_backtest_service.py`, `test_replay_service.py`, `test_signal_service.py`
stub module attributes via `monkeypatch` (`get_yfinance_data`, `calculate_signals`,
`AsyncSessionLocal`). Follow that pattern; never hit live services.
