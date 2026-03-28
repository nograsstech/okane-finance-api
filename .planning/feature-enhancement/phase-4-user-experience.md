# Phase 4: User Experience

**Status:** Pending
**Estimated Duration:** Week 11-13

---

## Overview

This phase implements user-facing features including strategy comparison tools, paper trading mode, and an analytics dashboard.

---

## 4.1 Strategy Comparison UI

### New Router: `app/signals/router_comparison.py`

**Purpose:** Allow users to compare multiple strategies across multiple tickers.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/signals/comparison/` | Create new comparison |
| GET | `/signals/comparison/{comparison_id}` | Get comparison results |
| GET | `/signals/comparison/metrics/available` | List available metrics |

**Request DTO:**
```python
class ComparisonRequestDTO(BaseModel):
    name: str
    tickers: list[str]
    strategies: list[str]
    period: str = "1y"
    interval: str = "1d"
    cash: float = 10000
    commission: float = 0.002
```

**Response DTO:**
```python
class ComparisonResponseDTO(BaseModel):
    comparison_id: str
    name: str
    results: list[dict]  # Each dict contains strategy results
    ranking: list[dict]  # Sorted by selected metric
    metrics: dict  # Best performing for each metric
```

**Available Metrics:**

| Metric | Label | Higher Better |
|--------|-------|---------------|
| return_pct | Return % | Yes |
| sharpe_ratio | Sharpe Ratio | Yes |
| sortino_ratio | Sortino Ratio | Yes |
| max_drawdown | Max Drawdown | No |
| win_rate | Win Rate % | Yes |
| profit_factor | Profit Factor | Yes |
| calmar_ratio | Calmar Ratio | Yes |
| average_trade | Avg Trade | Yes |

**Background Task:**
Comparisons run as background tasks to avoid blocking.

---

## 4.2 Paper Trading Mode

### New Router: `app/signals/router_paper_trading.py`

**Purpose:** Allow users to practice trading without real money.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/signals/paper-trading/portfolios` | Create portfolio |
| GET | `/signals/paper-trading/portfolios` | List user portfolios |
| GET | `/signals/paper-trading/portfolios/{id}` | Get portfolio details |
| POST | `/signals/paper-trading/trades` | Place trade |
| GET | `/signals/paper-trading/portfolios/{id}/trades` | List portfolio trades |
| POST | `/signals/paper-trading/trades/{id}/close` | Close trade |
| GET | `/signals/paper-trading/portfolios/{id}/performance` | Get performance metrics |

**DTOs:**

```python
class CreatePortfolioDTO(BaseModel):
    name: str
    initial_capital: float
    user_id: str = "default"

class PlaceTradeDTO(BaseModel):
    portfolio_id: int
    ticker: str
    strategy: str
    action: Literal["BUY", "SELL", "SHORT"]
    quantity: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
```

**Performance Metrics:**
- Total trades
- Total PnL
- Win rate
- Best trade
- Worst trade
- Average trade
- Current exposure
- Available capital

---

## 4.3 Analytics Dashboard

### New Router: `app/signals/router_analytics.py`

**Purpose:** Provide comprehensive analytics for strategies and portfolios.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/signals/analytics/dashboard` | Dashboard summary |
| GET | `/signals/analytics/strategy/{strategy}/ticker/{ticker}` | Strategy analytics |
| GET | `/signals/analytics/top-strategies` | Top performers by metric |
| GET | `/signals/analytics/equity-curve` | Equity curve data |
| GET | `/signals/analytics/monthly-returns` | Monthly returns breakdown |

**Dashboard Summary:**
```python
class DashboardSummaryDTO(BaseModel):
    total_strategies: int
    active_strategies: int
    total_backtests: int
    avg_return: float
    avg_sharpe: float
    best_performing: dict
    worst_performing: dict
    recent_activity: list[dict]
```

**Strategy Analytics:**
```python
class StrategyAnalyticsDTO(BaseModel):
    strategy: str
    ticker: str
    period: str
    metrics: dict
    equity_curve: list[dict]
    drawdown_curve: list[dict]
    monthly_returns: list[dict]
    trade_distribution: dict
```

**Chart Data Format:**
```python
class PerformanceChartDTO(BaseModel):
    labels: list[str]
    returns: list[float]
    drawdowns: list[float]
    equity_curve: list[float]
```

---

## 4.4 Frontend Integration Notes

### API Response Format

All endpoints should return consistent JSON responses:

```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-03-12T00:00:00Z",
    "version": "1.0"
  }
}
```

### Error Handling

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid ticker symbol",
    "details": { ... }
  }
}
```

---

## 4.5 WebSocket Support (Optional)

### Real-time Updates

For paper trading and live monitoring:

```python
# Endpoint: /ws/portfolio/{portfolio_id}
# Events: trade_opened, trade_closed, price_update

@router.websocket("/ws/portfolio/{portfolio_id}")
async def portfolio_updates(websocket: WebSocket, portfolio_id: int):
    await websocket.accept()
    # Send updates when trades are opened/closed
```

---

## 4.6 File Structure

```
app/signals/
├── router_comparison.py       # NEW
├── router_paper_trading.py    # NEW
├── router_analytics.py        # NEW
└── dto.py                     # UPDATE with new DTOs
```

---

## 4.7 Checklist

- [ ] Create `router_comparison.py` with all endpoints
- [ ] Create `router_paper_trading.py` with all endpoints
- [ ] Create `router_analytics.py` with all endpoints
- [ ] Add new DTOs to `dto.py`
- [ ] Implement comparison background task
- [ ] Add portfolio performance calculations
- [ ] Implement monthly returns calculation
- [ ] Add equity curve generation
- [ ] Register routers in `main.py`
- [ ] Add OpenAPI documentation
- [ ] Create integration tests
- [ ] Document API with examples

---

## 4.8 Dependencies

No new dependencies required.

---

**Previous Phase:** [Phase 3: Risk Management](./phase-3-risk-management.md)
**Next Phase:** [Phase 5: Platform Reliability](./phase-5-platform-reliability.md)
