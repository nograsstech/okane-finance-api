# Quick Start: Adding a New Strategy

This is a minimal guide to get you started with creating a new trading strategy.

## 5-Minute Guide

### 1. Create Strategy Folder

```bash
mkdir -p app/signals/strategies/my_strategy
touch app/signals/strategies/my_strategy/__init__.py
```

### 2. Create Signal Function

Create `app/signals/strategies/my_strategy/my_strategy.py`:

```python
import pandas as pd
import pandas_ta as ta

def my_strategy_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    # Get parameters
    period = parameters.get('period', 20)

    # Calculate indicators
    df.ta.ema(length=period, append=True)
    df.ta.rsi(length=14, append=True)

    # Generate signals: 2 (buy), 0 (hold), 1 (sell)
    df['TotalSignal'] = 0  # Hold
    df.loc[df[f'EMA_{period}'] > df['Close'], 'TotalSignal'] = 2  # Buy
    df.loc[df[f'EMA_{period}'] < df['Close'], 'TotalSignal'] = 1  # Sell

    return df
```

### 3. Create Backtest Function

Create `app/signals/strategies/my_strategy/my_strategy_backtest.py`:

```python
from backtesting import Backtest, Strategy
import pandas as pd
from .my_strategy import my_strategy_signals

class MyStrategy(Strategy):
    init_period = 20

    def init(self):
        self.period = self.params.get('period', 20)

    def next(self):
        if self.data.Close[-1] > self.data.Close[-2]:
            self.buy()

def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    # Calculate signals
    df = my_strategy_signals(df, strategy_parameters)
    dftest = df.dropna(subset=['TotalSignal']).copy()

    # Run backtest
    bt = Backtest(dftest, MyStrategy, cash=100000, margin=1/500, finalize_trades=True)
    bt.run()

    # Extract results
    stats = bt.stats
    trades = bt.trades
    trade_actions = []

    for trade in trades:
        trade_actions.append({
            'datetime': trade.EntryBar.strftime("%Y-%m-%d %H:%M:%S.%f"),
            'trade_action': 'buy' if trade.Size > 0 else 'sell',
            'price': trade.EntryPrice,
            'size': abs(trade.Size),
        })

    return bt, stats, trade_actions, strategy_parameters
```

### 4. Register Your Strategy

Edit `app/signals/strategies/register_strategies.py`:

Add at top:
```python
from .my_strategy.my_strategy import my_strategy_signals
from .my_strategy.my_strategy_backtest import backtest as my_strategy_backtest
```

Add to list in `register_all_strategies()`:
```python
("my_strategy", my_strategy_signals, my_strategy_backtest, "My Strategy", None),
```

### 5. Add Configuration

Edit `app/signals/strategies/config.py`:

```python
"my_strategy": StrategyConfig(
    name="my_strategy",
    display_name="My Strategy",
    default_size=0.03,
    requires_daily_data=False,
    default_parameters={"period": 20},
),
```

### 6. Test It

```bash
curl "http://localhost:8000/signals/backtest?ticker=AAPL&interval=1h&period=90d&strategy=my_strategy&parameters={\"period\":20}"
```

## Complete Working Example

See `app/signals/strategies/ema_bollinger/` for a complete working example.

## Common Indicators (pandas-ta)

```python
import pandas_ta as ta

# Moving averages
df.ta.sma(length=20, append=True)
df.ta.ema(length=20, append=True)

# RSI
df.ta.rsi(length=14, append=True)

# MACD
df.ta.macd(fast=12, slow=26, signal=9, append=True)

# Bollinger Bands
df.ta.bollinger(length=20, std=2, append=True)

# ATR
df.ta.atr(length=14, append=True)
```

## Parameter Handling

```python
def my_strategy_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    # Extract with defaults
    short_period = parameters.get('short_period', 12)
    long_period = parameters.get('long_period', 26)
    rsi_period = parameters.get('rsi_period', 14)

    # Use in calculations
    df.ta.ema(length=short_period, append=True)
    df.ta.rsi(length=rsi_period, append=True)

    return df
```

## Signal Values

- **2** = Buy/Long signal
- **0** = Hold/Square signal
- **1** = Sell/Short signal
