# Phase 3: Risk Management

**Status:** Pending
**Estimated Duration:** Week 7-10

---

## Overview

This phase implements comprehensive risk management features including position sizing strategies, portfolio optimization, risk analytics, and enhanced exit strategies.

---

## 3.1 Advanced Position Sizing

### New File: `app/signals/position_sizing.py`

**Purpose:** Calculate optimal position sizes based on various risk management strategies.

**Strategies to Implement:**

| Strategy | Description | Formula |
|----------|-------------|---------|
| Fixed Percentage | Fixed % of account | Position = Account × % |
| Kelly Criterion | Optimal growth rate | f = (W - (1-W)/R) × fraction |
| Risk Parity | Equal risk contribution | Position = (Account × Risk%) / (Entry - Stop) |
| Volatility Adjusted | Scale by volatility | Adjust base % by vol ratio |
| ATR Based | Volatility stops | Position = (Account × Risk%) / (ATR × mult) |

**Base Interface:**
```python
class PositionSizingStrategy:
    def __init__(
        self,
        account_balance: float,
        max_position_pct: float = 0.25,
        risk_per_trade: float = 0.02
    ):
        self.account_balance = account_balance
        self.max_position_pct = max_position_pct
        self.risk_per_trade = risk_per_trade

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        volatility: Optional[float] = None
    ) -> float:
        """Calculate position size based on strategy."""
```

**Factory Function:**
```python
def calculate_position_size(
    strategy: Literal["fixed", "kelly", "risk_parity", "volatility", "atr"],
    account_balance: float,
    entry_price: float,
    stop_loss: float,
    **kwargs
) -> float:
    """Factory function for position sizing."""
```

---

## 3.2 Portfolio Optimization

### New Directory: `app/signals/portfolio/`

**Structure:**
```
app/signals/portfolio/
├── __init__.py
├── optimizer.py      # Portfolio optimization algorithms
├── allocation.py     # Asset allocation strategies
├── rebalancer.py     # Rebalancing logic
└── backtester.py     # Portfolio-level backtesting
```

### Optimizer (`optimizer.py`)

**Optimization Methods:**

| Method | Description | Use Case |
|--------|-------------|----------|
| Mean-Variance | Markowitz optimization | Maximize Sharpe ratio |
| Risk Parity | Equal risk contribution | Diversified risk |
| Equal Weight | Simple allocation | Baseline comparison |

**Data Class:**
```python
@dataclass
class AssetData:
    ticker: str
    strategy: str
    returns: pd.Series
    volatility: float
    sharpe_ratio: float
```

**Result Class:**
```python
@dataclass
class PortfolioOptimizationResult:
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    allocations: list[dict]
```

**Mean-Variance Optimizer:**
```python
class MeanVarianceOptimizer:
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        min_weight: float = 0.0,
        max_weight: float = 0.5,
        max_assets: int = 10
    ):
    def optimize(self, assets: list[AssetData], returns_data: pd.DataFrame):
```

### Portfolio Backtester (`backtester.py`)

**Metrics to Calculate:**
- Total return
- Annualized return
- Volatility
- Sharpe ratio
- Max drawdown
- Calmar ratio
- Win rate
- Asset-level returns
- Equity curve
- Drawdown curve

---

## 3.3 Risk Analytics

### New File: `app/signals/risk_analytics.py`

**Purpose:** Calculate comprehensive risk metrics for strategies and portfolios.

**Metrics:**

| Metric | Description | Calculation |
|--------|-------------|-------------|
| VaR 95% | Value at Risk 95% | 5th percentile of returns |
| VaR 99% | Value at Risk 99% | 1st percentile of returns |
| CVaR 95% | Conditional VaR | Average of returns below VaR |
| Beta | Market sensitivity | Cov(r_p, r_m) / Var(r_m) |
| Alpha | Excess return | r_p - (r_f + β(r_m - r_f)) |
| Information Ratio | Risk-adjusted excess return | (r_p - r_b) / tracking_error |
| Tail Ratio | Upside vs downside | 95th / \|5th\| percentile |
| Common Sense Ratio | Profitability | (Win% × AvgWin) / (Loss% × \|AvgLoss\|) |
| Max Consecutive Losses | Drawdown streak | Max consecutive losses |

**Analyzer Class:**
```python
class RiskAnalyzer:
    def __init__(self, confidence_levels: list[float] = [0.95, 0.99]):

    def calculate_var(self, returns: pd.Series, confidence: float) -> float:

    def calculate_cvar(self, returns: pd.Series, confidence: float) -> float:

    def calculate_beta_alpha(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> tuple[float, float]:

    def calculate_information_ratio(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:

    def calculate_tail_ratio(self, returns: pd.Series) -> float:

    def calculate_common_sense_ratio(self, trades: list[dict]) -> float:

    def analyze(
        self,
        returns: pd.Series,
        trades: Optional[list[dict]] = None,
        benchmark_returns: Optional[pd.Series] = None
    ) -> RiskMetrics:
```

**Monte Carlo Simulation:**
```python
def run_monte_carlo_simulation(
    returns: pd.Series,
    n_simulations: int = 1000,
    n_days: int = 252,
    initial_capital: float = 100000
) -> dict:
    """
    Run Monte Carlo simulation for portfolio returns.

    Returns distribution statistics for risk analysis.
    """
```

---

## 3.4 Enhanced Exit Strategies

### New File: `app/signals/strategies/exit_strategies.py`

**Purpose:** Implement sophisticated exit strategies to protect profits and limit losses.

**Exit Strategies:**

| Strategy | Description | Parameters |
|----------|-------------|------------|
| Trailing Stop | Follows price up | trailing_pct, activation_pct |
| Break-Even Stop | Moves to entry after profit | activation_pct |
| Time-Based Exit | Exit after time period | max_hold_time, exit_time |
| Percentage Target | Fixed profit target | target_percent |
| Volatility-Based | ATR-adjusted stops | atr_multiplier |
| Composite | Combines multiple strategies | list of strategies |

**Signal Class:**
```python
@dataclass
class ExitSignal:
    action: Literal["HOLD", "CLOSE", "TRAIL_STOP", "BREAK_EVEN"]
    price: Optional[float] = None
    reason: str = ""
```

**Trailing Stop Implementation:**
```python
class TrailingStopLoss:
    def __init__(
        self,
        trailing_percent: float = 0.02,
        activation_percent: float = 0.01
    ):
    def update(self, current_price: float, entry_price: float) -> ExitSignal:
```

**Break-Even Stop Implementation:**
```python
class BreakEvenStop:
    def __init__(
        self,
        activation_percent: float = 0.02,
        original_stop: Optional[float] = None
    ):
    def update(
        self,
        current_price: float,
        entry_price: float,
        original_stop_price: float
    ) -> ExitSignal:
```

**Time-Based Exit:**
```python
class TimeBasedExit:
    def __init__(
        self,
        max_hold_time: str = "5d",
        exit_time: Optional[str] = None
    ):
    def on_entry(self, entry_time: pd.Timestamp) -> None:
    def update(self, current_time: pd.Timestamp) -> ExitSignal:
```

**Percentage Target:**
```python
class PercentageTarget:
    def __init__(self, target_percent: float = 0.05):
    def update(self, current_price: float, entry_price: float) -> ExitSignal:
```

**Volatility-Based Exit:**
```python
class VolatilityBasedExit:
    def __init__(
        self,
        atr_multiplier: float = 2.0,
        lookback_period: int = 14
    ):
    def on_entry(self, entry_price: float, df: pd.DataFrame, is_long: bool = True):
    def update(self, current_price: float) -> ExitSignal:
```

**Composite Strategy:**
```python
class CompositeExitStrategy:
    def __init__(self, strategies: list):
    def on_entry(self, entry_price: float, entry_time: pd.Timestamp, df: Optional[pd.DataFrame] = None):
    def update(self, current_price: float, current_time: pd.Timestamp, entry_price: float) -> ExitSignal:
```

---

## 3.5 Integration with Existing Strategies

### Update Strategy Files

Each strategy in `app/signals/strategies/` should be updated to:

1. Accept position sizing configuration
2. Support multiple exit strategies
3. Track risk metrics during backtesting
4. Support portfolio-level optimization

---

## 3.6 Checklist

- [ ] Create `position_sizing.py` with all strategies
- [ ] Create `portfolio/` directory structure
- [ ] Implement `optimizer.py` with 3 optimization methods
- [ ] Implement `backtester.py` with portfolio metrics
- [ ] Create `risk_analytics.py` with all risk metrics
- [ ] Implement Monte Carlo simulation
- [ ] Create `exit_strategies.py` with all exit types
- [ ] Update existing strategies to use position sizing
- [ ] Update existing strategies to use exit strategies
- [ ] Add unit tests for position sizing
- [ ] Add unit tests for portfolio optimization
- [ ] Add unit tests for risk analytics
- [ ] Add unit tests for exit strategies
- [ ] Document API endpoints for portfolio features
- [ ] Create example portfolios for testing

---

## 3.7 Dependencies

```toml
[tool.poetry.dependencies]
scipy = "^1.11.0"
numpy = "^1.24.0"
```

---

**Previous Phase:** [Phase 2: Trading Accuracy](./phase-2-trading-accuracy.md)
**Next Phase:** [Phase 4: User Experience](./phase-4-user-experience.md)
