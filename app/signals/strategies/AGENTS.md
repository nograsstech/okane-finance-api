# Strategy modules

One directory per strategy: `<name>_signals.py` (signal generation) and
`<name>_backtest.py` (backtesting). Public strategy IDs live in
`strategy_list.py` and may differ from package names (digits cannot start a
Python identifier).

## Adding or changing a strategy

Follow `docs/adding-a-strategy.md` at the repository root. It defines the
signals/backtest signatures, the four-value backtest return, and the three
registration points (`calculate.py`, `perform_backtest.py`, `strategy_list.py`).

## Worker safety

- `__init__.py` forces `backtesting.Pool` to a thread pool. Never call
  `multiprocessing.set_start_method` or create process pools here — that
  combination deadlocked backtest workers in production.
- Every `backtest()` must accept `skip_optimization`; the worker-safety test
  enforces it by reflection over dispatcher exports.
- Import-time code runs inside the bounded `BACKTEST_EXECUTOR`; keep it cheap
  and side-effect free.

## Signal contract

Signals output a DataFrame copy with a `TotalSignal` column: `0` none, `1` sell,
`2` buy. Backtests and persistence read this column; no other coupling exists
between the two files.
