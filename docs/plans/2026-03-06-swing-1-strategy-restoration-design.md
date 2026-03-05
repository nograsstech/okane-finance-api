# Swing-1 Strategy Restoration Design

**Date:** 2026-03-06
**Status:** Approved
**Commit:** 0ae29ccf1981aafc8b6de7e78261c3a8d3a5c6f7

## Context

The swing_1 trading strategy was previously added to the codebase but was reverted during a repository reset. The revert was not due to any issues with the strategy itself. This design documents the restoration of the complete swing_1 strategy implementation.

## Overview

The swing_1 strategy is a support/resistance pattern-based trading system that:
- Detects pivot-based and cluster-based S/R zones
- Recognizes candlestick patterns using TA-Lib
- Filters signals based on zone proximity
- Implements ATR-based risk management
- Provides comprehensive backtesting and signal generation

## Architecture

### New Directory Structure

```
app/signals/strategies/swing_1/
├── __init__.py              # Package initialization
├── constants.py             # Strategy parameters and definitions
├── risk_manager.py          # RiskManager class
├── swing.py                 # SwingSRStrategy (main backtesting strategy)
├── swing_backtest.py        # Backtest wrapper and optimization
└── swing_signals.py         # Signal calculation for API
```

### Integration Points

**Existing files to modify:**
1. `app/main.py` - Add CORS regex pattern
2. `app/signals/strategies/calculate.py` - Add swing_1 routing
3. `app/signals/strategies/perform_backtest.py` - Add swing_1 backtest routing
4. `app/signals/strategies/strategy_list.py` - Add "swing-1" to list

## Components

### 1. Constants (`constants.py`)

**Purpose:** Centralized strategy parameters and pattern definitions

**Key parameters:**
- `ATR_STOP_MULTIPLIER = 2.0` - ATR multiplier for stop-loss
- `RISK_REWARD_RATIO = 2.0` - TP/SL ratio
- `RISK_PER_TRADE = 0.02` - 2% equity risk per trade
- `ZONE_THRESHOLD = 0.03` - Zone proximity threshold (3%)
- `SR_ZONE_THRESHOLD = 0.015` - Zone merge threshold
- `SR_PATTERN_ZONE_PROXIMITY = 0.02` - Pattern-zone matching distance

**Pattern definitions:**
- 19 candlestick patterns (bullish and bearish)
- Pattern labels for display
- Pattern weights for reliability scoring
- Visualization colors for zones

### 2. Risk Manager (`risk_manager.py`)

**Purpose:** Calculate position size, stop-loss, and take-profit

**Key class:**
```python
class RiskManager:
    def __init__(self, atr_multiplier, risk_reward_ratio, risk_per_trade)
    def evaluate(self, equity, price, atr, direction) -> Dict
```

**Returns:**
- `size`: Position size (0-1 fraction of equity)
- `sl`: Stop-loss price
- `tp`: Take-profit price

### 3. Core Strategy (`swing.py`)

**Purpose:** Main backtesting.py Strategy implementation

**Key functions:**
- `identify_zones()` - Detect pivot and cluster S/R zones
- `build_price_action_patterns()` - Add candlestick pattern columns
- `SwingSRStrategy` class - Full strategy with init/next/plot methods

**Strategy logic:**
1. Identify S/R zones from price pivots and clusters
2. Detect candlestick patterns at each bar
3. When price nears a zone and appropriate pattern fires:
   - Long: Bullish pattern + near support zone
   - Short: Bearish pattern + near resistance zone
4. Use RiskManager for position sizing
5. Implement ATR-based stops and targets

### 4. Backtest Wrapper (`swing_backtest.py`)

**Purpose:** Run and optimize backtests

**Key function:**
```python
def backtest(df, strategy_parameters, size=0.03,
             skip_optimization=False, best_params=None)
```

**Optimization parameters:**
- `slcoef`: [1.0 to 5.0] - ATR stop multiplier
- `TPSLRatio`: [1.5 to 2.5] - Risk-reward ratio
- Maximizes: Win Rate [%]

**Returns:**
- Backtest object
- Stats dictionary
- Trade actions list
- Final strategy parameters

### 5. Signal Generator (`swing_signals.py`)

**Purpose:** Calculate TotalSignal for API endpoints

**Key function:**
```python
def swing_1_signals(df, parameters)
```

**Returns:**
- DataFrame with TotalSignal column (2=buy, 1=sell, 0=hold)

**Logic:**
1. Identify S/R zones
2. Detect candlestick patterns
3. Combine zone proximity + pattern type → signal
4. Output compatible with existing signal infrastructure

## Data Flow

### Backtesting Flow
```
User Request
  → POST /backtest
  → perform_backtest(strategy="swing-1")
  → swing_backtest.backtest()
  → SwingSRStrategy (backtesting.py)
  → RiskManager
  → Backtest results (stats, trades)
```

### Signal Generation Flow
```
User Request
  → POST /signals
  → calculate_signals(strategy="swing-1")
  → swing_1_signals()
  → identify_zones() + pattern detection
  → DataFrame with TotalSignal column
```

## Error Handling

**Graceful degradation:**
- TA-Lib optional: Patterns return 0 if not installed
- Matplotlib optional: Plotting disabled if not installed
- Empty/None DataFrames: Return empty results
- Insufficient data: Zone detection returns empty DataFrame

**Validation:**
- Check for None/empty input DataFrames
- Validate ATR > 0 before calculations
- Ensure price > 0 and equity > 0

## Testing Strategy

1. **Import verification** - All modules load without errors
2. **Signal generation** - Call `swing_1_signals()` with sample OHLCV data
3. **Backtest execution** - Run full backtest with optimization
4. **API integration** - Test `/backtest` and `/signals` endpoints with "swing-1"
5. **CORS verification** - Confirm regex allows additional domains

## Dependencies

**Required:**
- `numpy`, `pandas` - Data manipulation
- `scipy` - Signal processing for pivot detection
- `backtesting` - Strategy backtesting framework

**Optional (with graceful degradation):**
- `talib` - Candlestick pattern detection
- `matplotlib` - Chart plotting

## Success Criteria

- [ ] swing_1 directory created with all 6 files
- [ ] Integration files updated (main.py, calculate.py, perform_backtest.py, strategy_list.py)
- [ ] All imports resolve successfully
- [ ] Signal generation produces valid TotalSignal column
- [ ] Backtest runs without errors
- [ ] CORS regex pattern allows additional domains
- [ ] API endpoints accept "swing-1" strategy parameter
