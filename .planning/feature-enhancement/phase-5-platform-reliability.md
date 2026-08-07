# Phase 5: Platform Reliability

**Status:** Pending
**Estimated Duration:** Week 14-15

---

## Overview

This phase implements monitoring, caching, and comprehensive testing to ensure platform reliability and performance.

---

## 5.1 Monitoring & Alerts

### New Directory: `app/monitoring/`

**Structure:**
```
app/monitoring/
├── __init__.py
├── alerts.py         # Alert system
├── health.py         # Health checks
├── metrics.py        # Performance metrics
└── strategy_monitor.py # Strategy degradation detection
```

### Health Checks (`health.py`)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/` | Basic health check |
| GET | `/health/detailed` | Detailed system metrics |
| GET | `/health/database` | Database connectivity |
| GET | `/health/redis` | Redis connectivity |

**Metrics Included:**
- CPU usage
- Memory usage
- Disk usage
- Database connection status
- MongoDB connection status
- Redis connection status

```python
@router.get("/detailed")
async def detailed_health_check() -> dict:
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent
        },
        "databases": {
            "postgresql": "healthy",
            "mongodb": "healthy",
            "redis": "healthy"
        }
    }
```

### Strategy Monitor (`strategy_monitor.py`)

**Purpose:** Monitor strategy performance and send alerts on degradation.

**Health Class:**
```python
@dataclass
class StrategyHealth:
    strategy: str
    ticker: str
    status: Literal["HEALTHY", "DEGRADED", "CRITICAL"]
    current_sharpe: Optional[float]
    historical_sharpe: Optional[float]
    current_win_rate: Optional[float]
    historical_win_rate: Optional[float]
    degradation_pct: float
    last_check: datetime
```

**Monitor Class:**
```python
class StrategyMonitor:
    def __init__(
        self,
        sharpe_threshold: float = 1.0,
        win_rate_threshold: float = 0.40,
        degradation_threshold: float = 0.30,
        check_interval_hours: int = 24
    ):
    async def check_all_strategies(self) -> list[StrategyHealth]:
    async def check_strategy(self, strategy: str, ticker: str) -> StrategyHealth:
    async def send_alert(self, health: StrategyHealth) -> None:
```

**Scheduler:**
```python
class HealthCheckScheduler:
    def __init__(self, monitor: StrategyMonitor):
    async def start(self):
    def stop(self):
```

---

## 5.2 Performance Caching

### New Directory: `app/cache/`

**Structure:**
```
app/cache/
├── __init__.py
├── redis_client.py   # Redis connection
├── price_cache.py    # Price data caching
└── signal_cache.py   # Signal caching
```

### Redis Client (`redis_client.py`)

```python
class RedisClient:
    """Async Redis client wrapper."""

    _instance: Optional[aioredis.Redis] = None

    @classmethod
    async def get_client(cls) -> aioredis.Redis:

    @classmethod
    async def close(cls) -> None:
```

**Functions:**
- `get_cache(key)` - Get cached value
- `set_cache(key, value, expiration_seconds)` - Set cached value
- `get_json(key)` - Get JSON from cache
- `set_json(key, value, expiration_seconds)` - Set JSON in cache
- `delete_cache(key)` - Delete cached value
- `delete_pattern(pattern)` - Delete keys matching pattern

### Price Cache (`price_cache.py`)

**Cache Key Format:** `price:{ticker}:{period}:{interval}`

**Functions:**
```python
async def get_cached_prices(
    ticker: str,
    period: str,
    interval: str
) -> Optional[pd.DataFrame]:

async def cache_prices(
    ticker: str,
    period: str,
    interval: str,
    df: pd.DataFrame,
    ttl_seconds: int = 300
) -> None:

async def invalidate_price_cache(ticker: Optional[str] = None) -> None:
```

**Cache TTL:**
- Intraday data: 1 minute
- Daily data: 5 minutes
- Historical data: 1 hour

---

## 5.3 Test Coverage

### New Test Files

**Structure:**
```
tests/
├── test_strategies/
│   ├── __init__.py
│   ├── test_strategies.py         # Strategy tests
│   ├── test_position_sizing.py    # Position sizing tests
│   ├── test_exit_strategies.py    # Exit strategy tests
│   └── test_pattern_recognition.py # Pattern tests
├── test_portfolio/
│   ├── __init__.py
│   ├── test_optimizer.py          # Portfolio optimization tests
│   └── test_backtester.py         # Portfolio backtest tests
├── test_risk/
│   ├── __init__.py
│   └── test_risk_analytics.py     # Risk analytics tests
├── test_integration/
│   ├── __init__.py
│   ├── test_paper_trading.py      # Paper trading integration
│   └── test_comparison.py         # Strategy comparison integration
└── conftest.py                     # Shared fixtures
```

### Test Fixtures (`conftest.py`)

```python
@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    return pd.DataFrame({
        'Open': np.random.uniform(90, 110, 100),
        'High': np.random.uniform(100, 120, 100),
        'Low': np.random.uniform(80, 95, 100),
        'Close': np.random.uniform(90, 110, 100),
        'Volume': np.random.randint(1000000, 10000000, 100)
    }, index=dates)

@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Test Categories

#### Unit Tests

**Advanced Indicators:**
```python
class TestAdvancedIndicators:
    def test_stochastic_oscillator(self, sample_ohlcv):
    def test_williams_r(self, sample_ohlcv):
    def test_atr_calculation(self, sample_ohlcv):
```

**Pattern Recognition:**
```python
class TestPatternRecognition:
    def test_engulfing_pattern_detection(self, sample_ohlcv):
    def test_doji_detection(self, sample_ohlcv):
    def test_hammer_hanging_man(self, sample_ohlcv):
```

**Position Sizing:**
```python
class TestPositionSizing:
    def test_fixed_percentage_sizing(self):
    def test_risk_parity_sizing(self):
    def test_kelly_criterion_sizing(self):
```

**Risk Analytics:**
```python
class TestRiskAnalytics:
    def test_var_calculation(self, sample_returns):
    def test_cvar_calculation(self, sample_returns):
    def test_tail_ratio(self, sample_returns):
```

**Exit Strategies:**
```python
class TestExitStrategies:
    def test_trailing_stop(self):
    def test_break_even_stop(self):
    def test_percentage_target(self):
```

#### Integration Tests

```python
@pytest.mark.integration
class TestPaperTradingIntegration:
    async def test_create_portfolio(self, client):
    async def test_place_trade(self, client):
    async def test_close_trade(self, client):

@pytest.mark.integration
class TestStrategyComparisonIntegration:
    async def test_create_comparison(self, client):
    async def test_get_comparison_results(self, client):
```

---

## 5.4 Monitoring Router

### New Router: `app/monitoring/router.py`

```python
from fastapi import APIRouter

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

from .health import router as health_router
from .alerts import router as alerts_router

router.include_router(health_router)
router.include_router(alerts_router)
```

---

## 5.5 Dependencies

```toml
[tool.poetry.dependencies]
redis = {extras = ["hiredis"], version = "^5.0.0"}
psutil = "^5.9.0"}

[tool.poetry.dev-dependencies]
pytest-asyncio = "^0.21.0"
pytest-mock = "^3.12.0"
```

---

## 5.6 Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_CACHE_TTL=300

# Monitoring Configuration
HEALTH_CHECK_INTERVAL=3600
STRATEGY_MONITOR_ENABLED=true
STRATEGY_DEGRADATION_THRESHOLD=0.30

# Alert Configuration
DISCORD_ALERT_WEBHOOK_URL=
ALERT_EMAIL_ENABLED=false
```

---

## 5.7 Checklist

- [ ] Create `monitoring/` directory structure
- [ ] Implement `health.py` with health endpoints
- [ ] Implement `strategy_monitor.py` with monitoring
- [ ] Implement `alerts.py` with alert system
- [ ] Create `cache/` directory structure
- [ ] Implement `redis_client.py`
- [ ] Implement `price_cache.py`
- [ ] Implement `signal_cache.py`
- [ ] Create comprehensive test suite
- [ ] Add integration tests
- [ ] Configure pytest for async tests
- [ ] Set up CI/CD test pipeline
- [ ] Document monitoring endpoints
- [ ] Set up alert notification channels

---

## 5.8 Deployment Notes

### Docker Compose for Monitoring

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

---

**Previous Phase:** [Phase 4: User Experience](./phase-4-user-experience.md)
**Back to:** [README](./README.md)
