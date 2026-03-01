# Trading Strategies Module

This module contains the trading signal generation and backtesting infrastructure for the Okane Finance API.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Folder Structure](#folder-structure)
- [Adding a New Strategy](#adding-a-new-strategy)
- [Strategy Components](#strategy-components)
- [Configuration](#configuration)
- [Testing](#testing)

---

## Architecture Overview

The strategies module uses a **registry pattern** for strategy discovery and a **unified dispatcher** for signal calculation and backtesting, eliminating code duplication and making the system easier to extend.

### Key Components

```
strategies/
├── base.py                    # Abstract StrategyInterface
├── registry.py                # StrategyRegistry for auto-discovery
├── adapters.py                # LegacySignalAdapter for backward compatibility
├── register_strategies.py     # Auto-registration of all strategies
├── config.py                  # Centralized configuration
├── calculate.py               # Signal dispatcher (delegates to unified_calculator)
├── perform_backtest.py        # Backtest dispatcher (delegates to unified_backtest)
├── unified_calculator.py      # Unified signal calculation
├── unified_backtest.py        # Unified backtest execution
└── <strategy_name>/           # Individual strategy implementations
    ├── <strategy_name>.py
    └── <strategy_name>_backtest.py
```

---

## Folder Structure

```
strategies/
├── __init__.py
├── base.py                          # StrategyInterface abstract base class
├── registry.py                      # StrategyRegistry for managing strategies
├── adapters.py                      # LegacySignalAdapter for wrapping existing functions
├── register_strategies.py           # Auto-registers all strategies on import
├── config.py                        # Centralized strategy configuration
├── calculate.py                     # Signal calculation dispatcher (legacy wrapper)
├── perform_backtest.py              # Backtest execution dispatcher (legacy wrapper)
├── unified_calculator.py            # Unified signal calculation implementation
├── unified_backtest.py              # Unified backtest execution implementation
├── strategy_list.py                 # List of available strategies
│
├── ema_bollinger/                   # Example: EMA Bollinger strategy
│   ├── __init__.py
│   ├── ema_bollinger.py             # Signal calculation function
│   └── ema_bollinger_backtest.py     # Backtest function
│
├── macd_1/                          # Example: MACD strategy (uses daily data)
│   ├── __init__.py
│   ├── macd_1.py                    # Signal calculation (takes df, df1d, parameters)
│   └── macd_1_backtest.py           # Backtest function
│
├── swing-1/                         # Example: Complex strategy with multiple files
│   ├── __init__.py
│   ├── constants.py                  # Strategy-specific constants
│   ├── risk_manager.py              # Risk management logic
│   ├── swing.py                     # Main strategy implementation
│   ├── swing_signals.py             # Signal calculation function
│   └── swing_backtest.py            # Backtest function
│
└── replay/                          # Predefined trade strategy for replay
    ├── __init__.py
    └── predefined_trade_strategy.py
```

---

## Adding a New Strategy

Follow these steps to add a new trading strategy:

### Step 1: Create Strategy Directory

Create a new directory for your strategy:

```bash
mkdir -p app/signals/strategies/my_new_strategy
touch app/signals/strategies/my_new_strategy/__init__.py
```

### Step 2: Implement Signal Calculation

Create `my_new_strategy.py` with a signal calculation function:

```python
"""
My New Strategy - Signal Calculation
"""
import pandas as pd
import pandas_ta as ta

def my_new_strategy_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """
    Calculate trading signals for My New Strategy.

    Args:
        df: OHLCV DataFrame with index as datetime
        parameters: Dictionary of strategy parameters

    Returns:
        DataFrame with TotalSignal column added (0 for hold, 1 for sell, 2 for buy)
    """
    # Extract parameters
    period = parameters.get('period', 20)

    # Calculate indicators
    df.ta.ema(length=period, append=True)
    df.ta.rsi(length=14, append=True)

    # Generate signals
    # Example: Buy when EMA crosses above price and RSI < 70
    df['TotalSignal'] = 0  # Hold
    df.loc[
        (df[f'EMA_{period}'] > df['Close']) &
        (df['RSI_14'] < 70),
        'TotalSignal'
    ] = 2  # Buy signal

    df.loc[
        (df[f'EMA_{period}'] < df['Close']) &
        (df['RSI_14'] > 30),
        'TotalSignal'
    ] = 1  # Sell signal

    return df
```

**Important Notes:**
- The function signature must be: `(df, parameters)` for most strategies
- If your strategy needs daily timeframe data (like MACD), use: `(df, df1d, parameters)`
- The function must add a `TotalSignal` column with values: `0` (hold), `1` (sell), or `2` (buy)
- Always return the modified DataFrame

### Step 3: Implement Backtest

Create `my_new_strategy_backtest.py` with a backtest function:

```python
"""
My New Strategy - Backtesting
"""
from backtesting import Backtest, Strategy
import pandas as pd

# Import your signal function
from .my_new_strategy import my_new_strategy_signals

class MyNewStrategy(Strategy):
    """Strategy class for backtesting."""

    init_period = 20  # Warmup period

    def init(self):
        """Initialize strategy indicators."""
        self.period = self.params.get('period', 20)

    def next(self):
        """Process each candle."""
        # Your trading logic here
        if self.data.Close[-1] > self.data.Close[-2]:
            self.buy()
        elif self.data.Close[-1] < self.data.Close[-2]:
            self.sell()


def backtest(
    df: pd.DataFrame,
    strategy_parameters: dict,
    size: float = 0.03,
    skip_optimization: bool = False,
    best_params: dict = None
) -> tuple:
    """
    Run backtest for My New Strategy.

    Args:
        df: DataFrame with OHLCV data and calculated signals
        strategy_parameters: Strategy parameters
        size: Position size (fraction of equity)
        skip_optimization: Whether to skip parameter optimization
        best_params: Pre-optimized parameters to use

    Returns:
        Tuple of (backtest_object, stats, trade_actions, strategy_parameters)
    """
    # Calculate signals first
    df = my_new_strategy_signals(df, strategy_parameters)

    # Filter out rows without signals
    dftest = df.dropna(subset=['TotalSignal']).copy()

    # Set up strategy parameters
    cash = 100000
    margin = 1/500

    # Run backtest
    bt = Backtest(
        dftest,
        MyNewStrategy,
        cash=cash,
        margin=margin,
        finalize_trades=True
    )

    # Run optimization if not skipped
    if not skip_optimization:
        stats = bt.optimize()
    else:
        bt.run()

    # Get results
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

### Step 4: Register Your Strategy

Edit `app/signals/strategies/register_strategies.py`:

1. Add imports at the top:
```python
from .my_new_strategy.my_new_strategy import my_new_strategy_signals
from .my_new_strategy.my_new_strategy_backtest import backtest as my_new_strategy_backtest
```

2. Add to the strategies list in `register_all_strategies()`:
```python
strategies = [
    # ... existing strategies ...
    ("my_new_strategy", my_new_strategy_signals, my_new_strategy_backtest, "My New Strategy", None),
]
```

### Step 5: Add Configuration (Optional but Recommended)

Edit `app/signals/strategies/config.py`:

```python
STRATEGY_CONFIGS: dict[str, StrategyConfig] = {
    # ... existing strategies ...
    "my_new_strategy": StrategyConfig(
        name="my_new_strategy",
        display_name="My New Strategy",
        default_size=0.03,
        requires_daily_data=False,
        default_parameters={"period": 20},
    ),
}
```

### Step 6: Update Strategy List

Edit `app/signals/strategies/strategy_list.py` to include your strategy (or it will be auto-discovered from the registry).

### Step 7: Test Your Strategy

Run the backtest endpoint to verify your strategy works:

```bash
curl "http://localhost:8000/signals/backtest?ticker=AAPL&interval=1h&period=90d&strategy=my_new_strategy&parameters={\"period\":20}"
```

---

## Strategy Components

### Signal Calculation Function

The signal calculation function is the core of your strategy. It should:

1. **Accept inputs:**
   - `df`: Primary timeframe OHLCV DataFrame
   - `df1d`: Daily timeframe DataFrame (optional, only if needed)
   - `parameters`: Dictionary of strategy parameters

2. **Calculate indicators** using pandas-ta or manual calculations

3. **Add a `TotalSignal` column** with values:
   - `2` = Buy signal
   - `0` = Hold/Square signal
   - `1` = Sell signal

4. **Return the modified DataFrame**

Example:

```python
def my_strategy_signals(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    # Get parameters
    short_period = parameters.get('short_period', 12)
    long_period = parameters.get('long_period', 26)

    # Calculate indicators
    df.ta.ema(length=short_period, append=True)
    df.ta.ema(length=long_period, append=True)

    # Generate signals
    df['TotalSignal'] = 0  # Hold
    df.loc[df[f'EMA_{short_period}'] > df[f'EMA_{long_period}'], 'TotalSignal'] = 2  # Buy
    df.loc[df[f'EMA_{short_period}'] < df[f'EMA_{long_period}'], 'TotalSignal'] = 1  # Sell

    return df
```

### Backtest Function

The backtest function wraps your signal calculation in the backtesting.py framework.

Key components:

1. **Signal Calculation**: Calculate signals first
2. **Data Preparation**: Drop rows without signals
3. **Strategy Class**: Inherit from `backtesting.Strategy`
4. **Configuration**: Set cash, margin, and parameters
5. **Execution**: Run `Backtest.run()` or `Backtest.optimize()`
6. **Results**: Extract stats and trades into a list

Example Strategy Class:

```python
class MyStrategy(Strategy):
    init_period = 20  # Minimum candles before trading starts

    def init(self):
        # Initialize indicators and parameters
        self.buy_threshold = self.params.get('buy_threshold', 0.7)
        self.sell_threshold = self.params.get('sell_threshold', 0.3)

    def next(self):
        # Executed on each candle
        # Available:
        # - self.data.Close (current close)
        # - self.data.High[-1], self.data.Low[-1] (current high/low)
        # - self.data.Close[-2] (previous close)
        # - self.position (current position)
        # - self.buy(), self.sell() to trade

        if self.data.Close[-1] > self.data.Close[-2]:
            if not self.position:
                self.buy(size=0.03)
```

---

## Configuration

Strategy configuration is centralized in `config.py`:

```python
@dataclass
class StrategyConfig:
    name: str
    display_name: str
    description: str | None = None
    default_size: float = 0.03
    requires_daily_data: bool = False
    default_parameters: dict[str, Any] = field(default_factory=dict)
```

### Available Configuration Functions

```python
from app.signals.strategies.config import (
    get_strategy_config,        # Get full configuration
    get_default_size,           # Get default position size
    get_strategy_display_name,  # Get display name
    requires_daily_data,         # Check if daily data is needed
)
```

### Example Usage

```python
from app.signals.strategies.config import get_strategy_config

# Get strategy configuration
config = get_strategy_config("ema_bollinger")
print(config.display_name)  # "EMA Bollinger"
print(config.default_size)   # 0.03
print(config.default_parameters)  # {}

# Get default size with special case for BTC-USD
from app.signals.strategies.config import get_default_size
size = get_default_size("ema_bollinger", "BTC-USD")  # 0.01
```

---

## Strategy Registry

The strategy registry provides a centralized way to access all strategies:

```python
from app.signals.strategies.registry import StrategyRegistry

# List all strategies
strategies = StrategyRegistry.list_all()
# ['ema_bollinger', 'ema_bollinger_1_low_risk', 'macd_1', ...]

# Get a specific strategy
strategy = StrategyRegistry.get("ema_bollinger")

# Check if a strategy is registered
is_registered = StrategyRegistry.is_registered("ema_bollinger")

# Clear registry (useful for testing)
StrategyRegistry.clear()
```

---

## Signal Calculation

### Using the Unified Calculator

```python
from app.signals.strategies.calculate import calculate_signals, calculate_signals_async
import pandas as pd

# Synchronous
df = ...  # Your OHLCV data
result = calculate_signals(df, df1d=None, strategy="ema_bollinger", parameters={})

# Asynchronous
result = await calculate_signals_async(df, df1d=None, strategy="ema_bollinger", parameters={})
```

### Direct Strategy Function Call

```python
from app.signals.strategies.ema_bollinger.ema_bollinger import ema_bollinger_signals

df = ...  # Your OHLCV data
parameters = {"short_period": 8, "long_period": 21}

result = ema_bollinger_signals(df, parameters)
```

---

## Backtesting

### Using the Unified Backtest Executor

```python
from app.signals.strategies.perform_backtest import perform_backtest
import pandas as pd

# Prepare data with signals
df = ...  # Your OHLCV data
df = calculate_signals(df, None, "ema_bollinger", {})

# Run backtest
bt, stats, trades, params = perform_backtest(
    df,
    strategy="ema_bollinger",
    parameters={"size": 0.03},
    skip_optimization=False,
    best_params=None
)

# Access results
print(stats["Return [%]"])
print(stats["Sharpe Ratio"])
```

### Direct Backtest Function Call

```python
from app.signals.strategies.ema_bollinger.ema_bollinger_backtest import backtest

df = ...  # Your OHLCV data
parameters = {"size": 0.03}

bt, stats, trades, params = backtest(df, parameters, size=0.03, skip_optimization=False, best_params=None)
```

---

## Testing Strategies

### Unit Test Example

```python
import pytest
import pandas as pd
from app.signals.strategies.my_new_strategy.my_new_strategy import my_new_strategy_signals

def test_my_new_strategy_generates_signals():
    # Create sample data
    df = pd.DataFrame({
        'Open': [100, 101, 102, 103, 104],
        'High': [102, 103, 104, 105, 106],
        'Low': [99, 100, 101, 102, 103],
        'Close': [101, 102, 103, 104, 105],
        'Volume': [1000, 1100, 1200, 1300, 1400],
    })

    # Calculate signals
    result = my_new_strategy_signals(df, {'period': 5})

    # Verify
    assert 'TotalSignal' in result.columns
    assert result['TotalSignal'].notna().any()  # Has at least one signal
```

### Integration Test

```python
import pytest
from app.signals.strategies.calculate import calculate_signals

def test_strategy_in_unified_calculator():
    from app.signals.strategies.unified_calculator import _STRATEGY_FUNCTIONS

    # Verify strategy is registered
    assert "my_new_strategy" in _STRATEGY_FUNCTIONS

    # Test through unified calculator
    df = pd.DataFrame({...})
    result = calculate_signals(df, None, "my_new_strategy", {})
    assert result is not None
```

---

## Common Patterns

### Using Daily Timeframe Data

Some strategies (like MACD) require daily timeframe data for context:

```python
def macd_1_signals(df: pd.DataFrame, df1d: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    # df1d contains daily OHLCV data
    # df contains primary timeframe data (e.g., 15m, 1h)

    # Use daily data for trend context
    df['daily_trend'] = df1d['Close'].rolling(50).mean()

    # ... rest of your logic
    return df
```

**Important:** If your strategy needs `df1d`, update the `_STRATEGIES_REQUIRING_DAILY_DATA` set in `unified_calculator.py`:

```python
_STRATEGIES_REQUIRING_DAILY_DATA = {"macd_1", "my_new_strategy"}
```

### Custom Backtest Signatures

Some strategies have unique parameter requirements (e.g., grid trading doesn't use `size`). Handle this in `unified_backtest.py`:

```python
_BACKTEST_FUNCTIONS = {
    "my_new_strategy": (my_new_strategy_backtest, 0),  # Standard signature
    "grid_trading": (grid_trading_backtest, 1),    # Special signature (no size)
}
```

---

## Best Practices

1. **Keep it simple:** Start with basic indicators and signals
2. **Use pandas-ta:** It has 130+ built-in indicators
3. **Document parameters:** Clearly explain what each parameter does
4. **Handle edge cases:** Check for empty DataFrames, missing values
5. **Use type hints:** Improve code clarity and IDE support
6. **Add tests:** Verify your signals and backtest work correctly
7. **Follow conventions:** Match the structure of existing strategies

---

## Troubleshooting

### Strategy Not Found

```
Strategy 'my_new_strategy' not found in registry
```

**Solution:** Ensure your strategy is registered in `register_strategies.py`

### Function Signature Errors

```
TypeError: my_strategy_signals() takes 2 positional arguments but 3 were given
```

**Solution:** Check if your strategy needs `df1d`. If not, use `(df, parameters)`. If yes, use `(df, df1d, parameters)` and add to `_STRATEGIES_REQUIRING_DAILY_DATA`.

### No Trades Generated

```
Backtest returned no results (no trades were executed)
```

**Solution:**
- Check that `TotalSignal` column has non-zero values
- Verify the backtest strategy class is calling `buy()` and `sell()`
- Ensure your data has sufficient candles for the `init_period`

### Divide by Zero in Sharpe Ratio

This is a known issue when backtest has no variance. It's been suppressed with a warning filter in `service.py`.

---

## API Endpoints

### Get Signals
```
GET /signals/?ticker={ticker}&interval={interval}&period={period}&strategy={strategy}&parameters={parameters}
```

### Run Backtest
```
GET /signals/backtest?ticker={ticker}&interval={interval}&period={period}&strategy={strategy}&parameters={parameters}
```

### List Strategies
```
GET /signals/strategies
```

---

## Additional Resources

- [pandas-ta Documentation](https://github.com/twopirllab/pandas-ta)
- [backtesting.py Documentation](https://kernc.github.io/backtesting.py/doc/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
