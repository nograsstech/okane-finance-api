# HMM Market Regime Analysis

## Overview

This module implements a **Hidden Markov Model (HMM)** for analyzing market regimes (Bull, Bear, Chop) based on price action. The algorithm uses a 3-state HMM with Bayesian updating to detect market conditions in real-time.

## Algorithm

### What is a Hidden Markov Model?

A Hidden Markov Model is a statistical model that:
- Assumes the system being modeled is a Markov process with hidden (unobserved) states
- Each state has probability distributions over observable variables
- Transitions between states follow probabilistic rules

### Regime States

The model identifies three market regimes:

| Regime | State | Characteristics | Trading Strategy |
|--------|-------|----------------|------------------|
| **Bull** | 1 | Positive momentum, lower volatility | Trend Following (Long) |
| **Bear** | -1 | Negative momentum, higher volatility | Trend Following (Short) |
| **Chop** | 0 | Low momentum, high volatility (noise) | Mean Reversion or Stay Out |

### Observables (Emissions)

Two standardized observables are calculated for each time period:

1. **Momentum Observable**
   - Raw: Rate of change (`roc(close, 1)`)
   - Smoothed: Exponential Moving Average (EMA) with lookback period
   - Standardized: `(value - SMA) / Standard Deviation`

2. **Volatility Observable**
   - Raw: Average True Range (ATR) with lookback period
   - Standardized: `(value - SMA) / Standard Deviation`

### Regime Parameters

Each regime has characteristic mean and standard deviation for both observables:

```python
# Bull Regime
momentum: μ=1.0, σ=1.0
volatility: μ=-0.5, σ=1.0

# Bear Regime
momentum: μ=-1.0, σ=1.0
volatility: μ=1.0, σ=1.0

# Chop Regime
momentum: μ=0.0, σ=0.5
volatility: μ=1.5, σ=1.0
```

### Bayesian Update Process

For each time step:
1. **Calculate Likelihoods**: Use Gaussian PDF to compute likelihood of observables under each regime
2. **Apply Transition Matrix**: Update prior probabilities using regime transition probabilities
3. **Calculate Posteriors**: Multiply prior × likelihood for each regime
4. **Normalize**: Ensure probabilities sum to 100%
5. **Determine Dominant Regime**: Select regime with highest probability

### Transition Matrix

Regime transition probabilities (configurable):

| From \ To | Bull | Bear | Chop |
|-----------|------|------|------|
| **Bull** | 80% | 4% | 16% |
| **Bear** | 4% | 80% | 16% |
| **Chop** | 20% | 20% | 60% |

*Remaining probability distributed proportionally (e.g., 1-0.80=0.20, with 0.20×0.2=0.04 to other states)*

## API Endpoint

### Get HMM Regime Probabilities

```http
GET /signals/hmm/regimes
```

**Authentication**: HTTP Basic Auth (username/password from `.env`)

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ticker` | string | **required** | Ticker symbol (e.g., AAPL, BTC-USD) |
| `period` | string | "365d" | Time period (e.g., 90d, 1y) |
| `interval` | string | "1d" | Data interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo |
| `start` | string | null | Start date (YYYY-MM-DD) |
| `end` | string | null | End date (YYYY-MM-DD) |
| `length` | integer | 20 | Lookback period for observable calculations |
| `p_stay_bull` | float | 0.80 | P(Bull\|Bull) transition probability |
| `p_stay_bear` | float | 0.80 | P(Bear\|Bear) transition probability |
| `p_stay_chop` | float | 0.60 | P(Chop\|Chop) transition probability |

**Example Request**:

```bash
curl -u "username:password" \
  "http://localhost:8000/signals/hmm/regimes?ticker=AAPL&period=90d&interval=1d"
```

**Response Structure**:

```json
{
  "status": 200,
  "message": "HMM regime data for AAPL",
  "data": [
    {
      "timestamp": "2026-03-20T00:00:00",
      "close": 247.99,
      "obs_momentum": -1.08,
      "obs_volatility": -2.18,
      "prob_bull": 97.99,
      "prob_bear": 1.85,
      "prob_chop": 0.16,
      "dominant_regime": "bull",
      "confidence_score": 97.99,
      "regime_state": 1
    }
  ],
  "summary": {
    "current_regime": "bull",
    "current_state": 1,
    "confidence": "HIGH",
    "confidence_score": 97.99,
    "prob_bull": 97.99,
    "prob_bear": 1.85,
    "prob_chop": 0.16,
    "recommended_strategy": "Trend Following (Long)"
  },
  "ticker": "AAPL",
  "interval": "1d",
  "data_points": 61
}
```

### Response Fields

**Data Point Fields**:
- `timestamp`: ISO 8601 datetime
- `close`: Close price
- `obs_momentum`: Standardized momentum observable
- `obs_volatility`: Standardized volatility observable
- `prob_bull`: Bull regime probability (0-100)
- `prob_bear`: Bear regime probability (0-100)
- `prob_chop`: Chop regime probability (0-100)
- `dominant_regime`: "bull", "bear", or "chop"
- `confidence_score`: Maximum probability (0-100)
- `regime_state`: 1 (bull), -1 (bear), 0 (chop)

**Summary Fields**:
- `current_regime`: Dominant regime for latest data point
- `current_state`: State code for latest data point
- `confidence`: "HIGH" (>70%), "MEDIUM" (>50%), "LOW" (≤50%)
- `confidence_score`: Latest confidence score
- `prob_bull`, `prob_bear`, `prob_chop`: Latest probabilities
- `recommended_strategy`: Trading strategy recommendation

## Usage Examples

### Python Client

```python
import requests
from requests.auth import HTTPBasicAuth

# Fetch HMM regime data
response = requests.get(
    "http://localhost:8000/signals/hmm/regimes",
    params={
        "ticker": "AAPL",
        "period": "365d",
        "interval": "1d"
    },
    auth=HTTPBasicAuth("username", "password")
)

data = response.json()

# Get current regime
print(f"Current regime: {data['summary']['current_regime']}")
print(f"Confidence: {data['summary']['confidence']} ({data['summary']['confidence_score']:.1f}%)")
print(f"Strategy: {data['summary']['recommended_strategy']}")

# Access time series
for point in data['data']:
    print(f"{point['timestamp']}: {point['dominant_regime']} ({point['confidence_score']:.1f}%)")
```

### JavaScript/TypeScript Client

```typescript
const auth = btoa('username:password');
const response = await fetch(
  'http://localhost:8000/signals/hmm/regimes?ticker=AAPL&period=365d&interval=1d',
  {
    headers: {
      'Authorization': `Basic ${auth}`
    }
  }
);

const data = await response.json();

console.log(`Current regime: ${data.summary.current_regime}`);
console.log(`Confidence: ${data.summary.confidence} (${data.summary.confidence_score.toFixed(1)}%)`);
console.log(`Strategy: ${data.summary.recommended_strategy}`);
```

## Implementation Details

### File Structure

```
app/signals/
├── signals_generator/
│   └── hmm_signals.py          # Core HMM calculation logic
├── hmm_service.py               # Service layer
├── hmm_dto.py                   # Pydantic models
└── router.py                    # API endpoint (modified)

tests/
└── test_hmm_signals.py          # Unit tests (24 tests)
```

### Core Functions

**`hmm_signals.py`**:
- `gaussian_pdf(x, mu, sigma)`: Gaussian probability density function
- `calculate_hmm_regime(df, params)`: Main HMM calculation
- `hmm_to_signal(df, threshold)`: Convert regimes to trading signals

**`hmm_service.py`**:
- `get_hmm_regime_data(...)`: Fetch market data and calculate HMM regimes

### Dependencies

- `numpy`: Numerical computations
- `pandas`: Data manipulation
- `pandas-ta`: Technical indicators (ROC, EMA, SMA, ATR, STDEV)
- `yfinance`: Market data fetching

No additional dependencies required (uses existing packages).

## Testing

Run unit tests:

```bash
pytest tests/test_hmm_signals.py -v
```

Expected output: 24 tests passing

## Algorithm Origin

This implementation is based on the Pine Script indicator:
**"Hidden Markov Model: Regime Probability [AlgoPoint]"** by Harmony Algo & AlgoPoint

The Python implementation exactly replicates the Pine Script algorithm:
- Same observable calculations
- Same regime parameters
- Same transition matrix logic
- Same Bayesian update process

## Confidence Levels

| Confidence Score | Level | Interpretation |
|------------------|-------|----------------|
| >70% | HIGH | Strong regime conviction, reliable signal |
| 50-70% | MEDIUM | Moderate conviction, use with confirmation |
| <50% | LOW | Low conviction, uncertain market state |

## Trading Recommendations

### Bull Market (Regime)
- **Strategy**: Trend Following (Long)
- **Tactics**: Buy dips, use trailing stops, pyramid positions
- **Avoid**: Short selling, mean reversion strategies

### Bear Market (Regime)
- **Strategy**: Trend Following (Short)
- **Tactics**: Short rallies, use tight stops, consider hedging
- **Avoid**: Buying dips, holding long positions

### Chop Market (Regime)
- **Strategy**: Mean Reversion or Stay Out
- **Tactics**: Range trading, mean reversion, or avoid trading
- **Avoid**: Trend following, breakout strategies

## Configuration Tips

### Lookback Period (`length`)
- **Default**: 20 periods
- **Shorter (10-15)**: More sensitive, faster regime detection, more false signals
- **Longer (30-50)**: Smoother, slower regime detection, fewer false signals

### Transition Probabilities
- **Default**: Bull/Bear stay=0.80, Chop stay=0.60
- **Higher stay probabilities**: More persistent regimes, slower regime changes
- **Lower stay probabilities**: More frequent regime changes

### Interval Selection
- **1d (Daily)**: Best for swing trading, position trading
- **1h (Hourly)**: Day trading, intraday analysis
- **1wk (Weekly)**: Long-term investing, macro analysis

## Performance Considerations

- **No caching**: Each request calculates fresh HMM results
- **Data fetching**: Uses yfinance (can be slow for large date ranges)
- **Computation**: O(n) where n = number of data points
- **Typical response time**: 1-5 seconds for 1-year daily data

## Limitations

1. **Lag effect**: Regime detection has inherent lag due to lookback period
2. **False signals**: Low confidence periods may produce false signals
3. **Data quality**: Depends on yfinance data quality and availability
4. **No adaptive learning**: Transition probabilities are fixed (not learned from data)

## Future Enhancements

Potential improvements for future versions:

1. **Adaptive transition matrix**: Learn transition probabilities from historical data
2. **Regime prediction**: Predict future regime changes
3. **Multi-asset correlation**: Analyze regime across multiple assets
4. **Caching**: Add MongoDB caching for frequently requested tickers
5. **Signal generation**: Add HMM-based trading signals for backtesting
6. **Confidence intervals**: Add uncertainty quantification
7. **Regime duration**: Track how long each regime persists

## License

This implementation follows the same license as the parent project.

## Credits

Algorithm based on Pine Script indicator by:
- **AlgoPoint** (https://www.algopoint.io)
- **Harmony Algo & AlgoPoint Collaboration**
