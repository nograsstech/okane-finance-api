# Phase 2: Trading Accuracy

**Status:** Pending
**Estimated Duration:** Week 3-6

---

## Overview

This phase focuses on improving signal accuracy through sentiment analysis, machine learning models, advanced technical indicators, and candlestick pattern recognition.

---

## 2.1 Sentiment-Aware Signals

### New File: `app/signals/signals_generator/sentiment_signals.py`

**Purpose:** Integrate news sentiment into signal generation for more informed trading decisions.

**Key Functions:**

```python
async def get_sentiment_for_ticker(
    ticker: str,
    period: str = "1d"
) -> float:
    """
    Fetch sentiment score for a ticker.

    Returns:
        float: Sentiment score between -1 (bearish) and 1 (bullish)
    """

def sentiment_adjusted_signal(
    base_signal: int,
    sentiment_score: float,
    threshold: float = 0.3
) -> int:
    """
    Adjust technical signal based on sentiment.

    Rules:
    - Strong positive sentiment (> threshold) can upgrade HOLD to BUY
    - Strong negative sentiment (< -threshold) can upgrade HOLD to SELL
    - Conflicting signals (e.g., BUY + negative sentiment) become HOLD
    """

async def generate_sentiment_enhanced_signals(
    df: pd.DataFrame,
    ticker: str,
    base_signals: pd.Series,
    sentiment_period: str = "1d"
) -> pd.Series:
    """Generate sentiment-enhanced signals."""
```

**Integration Point:** `app/signals/service.py`

```python
async def get_signals_with_sentiment(
    request: SignalRequestDTO,
    enable_sentiment: bool = True
) -> SignalResponseDTO:
    """Enhanced signal generation with sentiment integration."""
```

**Data Source:** `news_with_sentiment` collection in MongoDB

---

## 2.2 ML-Based Signal Models

### New Directory: `app/signals/ml_models/`

**Structure:**
```
app/signals/ml_models/
├── __init__.py
├── base.py                 # Base model interface
├── feature_engineering.py  # Feature creation
├── lstm_model.py           # LSTM implementation
├── random_forest_model.py  # Random Forest implementation
├── xgboost_model.py        # XGBoost implementation
├── trainer.py              # Training pipeline
└── predictor.py            # Inference endpoint
```

### Base Model Interface (`base.py`)

```python
class BaseMLModel(ABC):
    """Base interface for all ML models."""

    @abstractmethod
    async def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        """Train the model and return metrics."""

    @abstractmethod
    async def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to disk."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from disk."""
```

### Feature Engineering (`feature_engineering.py`)

**Features to create:**
- Price-based: returns, log_returns, high_low_ratio, close_open_ratio
- Volume: volume_change, volume_ma_ratio
- Moving averages: SMA 5, 10, 20, 50; EMA 5, 10, 20, 50
- Crossovers: MA cross signals
- RSI (14)
- MACD + signal + histogram
- Bollinger Bands: upper, middle, lower, width, position
- ATR (14)
- Stochastic: %K, %D
- Williams %R
- Lag features: returns_lag_1,2,3,5,10
- Volatility: rolling std for 5 and 20 periods

### LSTM Model (`lstm_model.py`)

**Architecture:**
- Input: (sequence_length, n_features)
- LSTM 1: 128 units, return_sequences=True, dropout=0.2
- BatchNormalization
- LSTM 2: 64 units, dropout=0.2
- BatchNormalization
- Dense: 32 units, ReLU, dropout=0.2
- Output: 3 units (HOLD, SELL, BUY), softmax

**Training:**
- Loss: sparse_categorical_crossentropy
- Optimizer: Adam (lr=0.001)
- Early stopping: patience=10
- Validation split: 20%

---

## 2.3 Additional Technical Indicators

### New File: `app/signals/signals_generator/advanced_indicators.py`

**Indicators to implement:**

| Indicator | Parameters | Description |
|-----------|------------|-------------|
| Stochastic Oscillator | k=14, d=3, smooth=3 | Momentum indicator |
| Williams %R | period=14 | Momentum indicator |
| ATR | period=14 | Volatility measure |
| OBV | - | Volume trend |
| Ichimoku Cloud | tenkan=9, kijun=26, senkou=52 | Trend following |
| Fibonacci Retracements | window=50 | Support/resistance levels |

**Signal Generation:**
```python
def generate_signals_from_stochastic(
    stoch_k: pd.Series,
    stoch_d: pd.Series,
    oversold: float = 20,
    overbought: float = 80
) -> pd.Series:
    """Generate signals based on Stochastic Oscillator."""
```

---

## 2.4 Pattern Recognition

### New File: `app/signals/signals_generator/pattern_recognition.py`

**Candlestick Patterns to Detect:**

| Pattern | Type | Description |
|---------|------|-------------|
| Bullish Engulfing | Reversal | Bullish trend reversal |
| Bearish Engulfing | Reversal | Bearish trend reversal |
| Doji | Neutral | Market indecision |
| Hammer | Reversal | Bullish reversal after downtrend |
| Hanging Man | Reversal | Bearish reversal after uptrend |
| Morning Star | Reversal | 3-candle bullish reversal |
| Evening Star | Reversal | 3-candle bearish reversal |

**Support/Resistance Detection:**
```python
def detect_support_resistance(
    df: pd.DataFrame,
    window: int = 20,
    tolerance: float = 0.02
) -> dict[str, pd.Series]:
    """
    Detect support and resistance levels using local extrema.

    Returns:
        dict with 'support', 'resistance', and signals
    """
```

**Combined Signals:**
```python
def combine_pattern_signals(
    engulfing: pd.Series,
    doji: pd.Series,
    hammer: pd.Series,
    stars: pd.Series,
    support_resistance: dict
) -> pd.Series:
    """Combine multiple pattern signals into unified signals."""
```

---

## 2.5 Integration with Existing Signals

### Update: `app/signals/signals_generator/__init__.py`

Export new signal generators:
```python
from .sentiment_signals import generate_sentiment_enhanced_signals
from .advanced_indicators import (
    stochastic_oscillator,
    williams_r,
    average_true_range,
    on_balance_volume,
    ichimoku_cloud,
    fibonacci_retracements
)
from .pattern_recognition import (
    detect_engulfing_pattern,
    detect_doji,
    detect_hammer_hanging_man,
    detect_morning_evening_star,
    detect_support_resistance,
    combine_pattern_signals
)
```

### Update: `app/signals/strategies/strategy_list.py`

Add new strategies that use:
- Sentiment-enhanced signals
- Pattern recognition
- Advanced indicators

---

## 2.6 Checklist

- [ ] Create `sentiment_signals.py` with sentiment integration
- [ ] Create `ml_models/` directory structure
- [ ] Implement `base.py` with BaseMLModel interface
- [ ] Implement `feature_engineering.py` with all features
- [ ] Implement `lstm_model.py` with LSTM architecture
- [ ] Implement `random_forest_model.py`
- [ ] Implement `xgboost_model.py`
- [ ] Implement `trainer.py` for training pipeline
- [ ] Implement `predictor.py` for inference
- [ ] Create `advanced_indicators.py` with all indicators
- [ ] Create `pattern_recognition.py` with candlestick patterns
- [ ] Update `__init__.py` to export new functions
- [ ] Add unit tests for each module
- [ ] Document API endpoints for ML predictions
- [ ] Create training data preparation scripts

---

## 2.7 Dependencies

```toml
[tool.poetry.dependencies]
tensorflow = "^2.15.0"
scikit-learn = "^1.4.0"
scipy = "^1.11.0"

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
```

---

**Previous Phase:** [Phase 1: Foundation](./phase-1-foundation.md)
**Next Phase:** [Phase 3: Risk Management](./phase-3-risk-management.md)
