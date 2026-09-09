# Adding a strategy

Every strategy is a pair of files in one package plus registration in three dispatch
points. The whole workflow is mechanical except the algorithm itself.

## 1. Create the package

```
app/signals/strategies/<strategy_name>/
├── __init__.py
├── <strategy_name>_signals.py
└── <strategy_name>_backtest.py
```

The package name must be a valid Python identifier. It cannot start with a digit.
The **public ID** (what API callers send) may differ from the package name:

| Package | Public ID |
|---|---|
| `five_min_orb` | `5_min_orb` |
| `five_min_orb_confirmation` | `5_min_orb_confirmation` |

Copy `five_min_orb` (signals + backtest) or `grid_trading` as the smallest template.

## 2. Write the signals module

```python
def <strategy_name>_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
```

Contract:

- Input `df` is OHLCV data from yfinance (see `app/signals/utils/yfinance.py`).
- Output is a copy of `df` with a `TotalSignal` column: `0` = no signal, `1` = sell,
  `2` = buy. Backtests read `TotalSignal`; without it they return no trades.
- Dual-timeframe strategies also receive a daily/4H frame (see `macd_1`,
  `mean_reversion_trend_filter`).
- Pure pandas/numpy. No network, no database, no logging side effects beyond
  `logger` calls.

## 3. Write the backtest module

```python
def backtest(
    df: pd.DataFrame,
    strategy_parameters: dict | None = None,
    size: float = 0.03,
    skip_optimization: bool = False,
    best_params: dict | None = None,
) -> tuple[Any, Any, list[dict], dict]:
```

Contract:

- Returns `(bt, stats, trade_actions, strategy_parameters)` — exactly four values.
- `skip_optimization` is **required**. `tests/test_backtest_worker_safety.py`
  asserts every `*_backtest` callable exported from
  `app/signals/strategies/perform_backtest.py` accepts it. When `True`, skip
  parameter optimization and use defaults.
- `trade_actions` is a list of dicts with `datetime`, `action`, `price` keys
  (persisted as `TradeAction` rows).

Worker-safety rules (violating these reintroduces fixed deadlocks):

- Never call `multiprocessing.set_start_method` at import time or anywhere else.
- Never create process pools. `app/signals/strategies/__init__.py` already forces
  `backtesting.Pool` to a thread pool (`multiprocessing.dummy`) — rely on it.
- Backtests run inside `BACKTEST_EXECUTOR` (5 threads, `app/executors.py`);
  import-time work must be cheap and side-effect free.

## 4. Register in three places

1. `app/signals/strategies/calculate.py` — import the signals function, add a
   dispatch case:
   ```python
   elif strategy == "<public_id>":
       return <strategy_name>_signals(df, parameters)
   ```
2. `app/signals/strategies/perform_backtest.py` — import `backtest as
   <strategy_name>_backtest`, add a dispatch case passing
   `skip_optimization` and `best_params` through.
3. `app/signals/strategies/strategy_list.py` — add the public ID. This list is
   the API contract; the DTO validator rejects anything not in it.

## 5. Tests

- `tests/test_<strategy_name>_signals.py` — signal logic on synthetic frames
  (pattern: `tests/test_five_min_orb_signals.py`).
- Backtest test — parameter defaults under `skip_optimization=True`
  (pattern: `test_backtest_worker_safety.py::test_legacy_backtests_supply_defaults_when_optimization_is_skipped`).
- No live yfinance, database, or notification calls in tests. Mock the boundaries.

## 6. Verify

```zsh
uv run pytest -m "not integration" --tb=short -q
uv run mypy
uv run ruff check <changed files>
```

Done when: all three pass, the new ID appears in `GET /signals/strategies`, and a
`GET /signals/backtest?ticker=...&strategy=<public_id>` smoke request returns stats.

## Reference

- `docs/codebase-map.html` — interactive module graph; click `strategies.calculate`
  or `strategies.perform_backtest` to see who imports them.
- `CLAUDE.md` — core boundaries and working constraints.
