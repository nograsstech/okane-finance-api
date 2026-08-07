# Dependencies

**Last Updated:** 2026-03-12

---

## Overview

This document lists all required dependencies for the feature enhancement plan, organized by phase and purpose.

---

## Core Dependencies (Already Installed)

These are already in the project:

```toml
[tool.poetry.dependencies]
python = "^3.13"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
pydantic = "^2.10.0"
sqlalchemy = "^2.0.36"
psycopg = {extras = ["async"], version = "^3.2.0"}
motor = "^3.6.0"
pandas = "^2.2.0"
numpy = "^1.26.0"
pandas-ta = {path = "vendor/pandas_ta-0.3.14b0-py3-none-any.whl"}
yfinance = "^0.2.50"
backtesting = "^0.3.2"
langchain = "^0.3.0"
langchain-google-genai = "^2.0.0"
```

---

## Phase 2: Trading Accuracy Dependencies

### Machine Learning

```toml
[tool.poetry.dependencies]
tensorflow = "^2.15.0"
scikit-learn = "^1.4.0"
xgboost = "^2.1.0"
```

**Purpose:**
- `tensorflow`: LSTM neural network implementation
- `scikit-learn`: Random Forest, preprocessing, utilities
- `xgboost`: XGBoost model implementation

### Scientific Computing

```toml
[tool.poetry.dependencies]
scipy = "^1.11.0"
joblib = "^1.4.0"
```

**Purpose:**
- `scipy`: Optimization, statistical functions
- `joblib`: Model serialization

---

## Phase 3: Risk Management Dependencies

```toml
[tool.poetry.dependencies]
scipy = "^1.11.0"  # Already listed above
```

**Purpose:**
- Portfolio optimization (scipy.optimize.minimize)
- Statistical calculations

---

## Phase 5: Platform Reliability Dependencies

### Caching

```toml
[tool.poetry.dependencies]
redis = {extras = ["hiredis"], version = "^5.0.0"}
```

**Purpose:**
- Price data caching
- Signal caching
- Session storage

### Monitoring

```toml
[tool.poetry.dependencies]
psutil = "^5.9.0"
```

**Purpose:**
- System health monitoring
- Resource usage tracking

---

## Development Dependencies

```toml
[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-mock = "^3.12.0"
pytest-cov = "^4.1.0"
httpx = "^0.27.0"  # For testing async endpoints
```

---

## Complete pyproject.toml Additions

Add the following to your existing `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# ... existing dependencies ...
# Phase 2: ML & Analytics
tensorflow = "^2.15.0"
scikit-learn = "^1.4.0"
xgboost = "^2.1.0"
scipy = "^1.11.0"
joblib = "^1.4.0"
# Phase 5: Caching & Monitoring
redis = {extras = ["hiredis"], version = "^5.0.0"}
psutil = "^5.9.0"

[tool.poetry.dev-dependencies]
# ... existing dependencies ...
pytest-asyncio = "^0.21.0"
pytest-mock = "^3.12.0"
pytest-cov = "^4.1.0"
```

---

## Installation Commands

### All Dependencies

```bash
uv sync --dev
```

### Phase-Specific

```bash
# Phase 2 only
uv add tensorflow scikit-learn xgboost scipy joblib

# Phase 5 only
uv add "redis[hiredis]" psutil
```

---

## Dependency Notes

### TensorFlow

TensorFlow 2.15+ supports Python 3.11. For Python 3.13, you may need:

```toml
tensorflow = "^2.16.0"  # Or later version with 3.13 support
```

Alternative: Use `tensorflow-cpu` if GPU support is not needed.

### Redis

For production, consider using `hiredis` for better performance:

```bash
uv add "redis[hiredis]"
```

### XGBoost

XGBoost may require additional system libraries:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# macOS
# Usually works out of the box
```

---

## Docker Considerations

### Dockerfile Updates

```dockerfile
# Add system dependencies for TensorFlow
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Redis client
RUN pip install "redis[hiredis]"

# Install ML libraries
RUN pip install tensorflow scikit-learn xgboost
```

---

## Version Constraints

| Package | Minimum | Recommended | Maximum |
|---------|---------|-------------|---------|
| tensorflow | 2.15.0 | 2.16.1 | 2.17.x |
| scikit-learn | 1.4.0 | 1.5.0 | 1.6.x |
| xgboost | 2.1.0 | 2.1.2 | 2.2.x |
| scipy | 1.11.0 | 1.13.0 | 1.14.x |
| redis | 5.0.0 | 5.2.0 | 5.x |
| psutil | 5.9.0 | 6.1.0 | 6.x |

---

## Optional Dependencies

### For Development

```toml
[tool.poetry.dev-dependencies]
# Code quality
ruff = "^0.8.0"
mypy = "^1.10.0"

# Documentation
mkdocs = "^1.6.0"
mkdocs-material = "^9.5.0"

# Jupyter for experimentation
jupyter = "^1.1.0"
ipykernel = "^6.29.0"
```

### For Production Monitoring

```toml
[tool.poetry.dependencies]
prometheus-client = "^0.21.0"
opentelemetry-api = "^1.27.0"
opentelemetry-sdk = "^1.27.0"
```

---

**Back to:** [README](./README.md)
