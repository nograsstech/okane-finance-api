# Phase 1: Foundation

**Status:** Pending
**Estimated Duration:** Week 1-2

---

## Overview

This phase establishes the database models and repository layer needed for all subsequent features. All new features depend on this foundation.

---

## 1.1 New Database Models

### File: `app/db/models.py` (Additions)

#### Portfolio Management Models

```python
# Portfolio Management
class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=False)  # For multi-user support
    initial_capital = Column(Float, nullable=False)
    current_capital = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    allocations = relationship("PortfolioAllocation", back_populates="portfolio")


class PortfolioAllocation(Base):
    __tablename__ = "portfolio_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"))
    ticker = Column(String(20), nullable=False)
    strategy = Column(String(50), nullable=False)
    weight = Column(Float, nullable=False)  # Portfolio weight
    position_size = Column(Float, nullable=False)

    portfolio = relationship("Portfolio", back_populates="allocations")
```

#### Paper Trading Models

```python
# Paper Trading
class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(BigInteger, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    ticker = Column(String(20), nullable=False)
    strategy = Column(String(50), nullable=False)
    action = Column(String(10), nullable=False)  # BUY/SELL/CLOSE
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)
    status = Column(String(20), default="OPEN")  # OPEN/CLOSED/CANCELLED
    entry_time = Column(DateTime, server_default=func.now())
    exit_time = Column(DateTime)
    pnl = Column(Float)
    pnl_percentage = Column(Float)
```

#### Strategy Comparison Models

```python
# Strategy Comparison
class StrategyComparison(Base):
    __tablename__ = "strategy_comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comparison_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    tickers = Column(ARRAY(String))
    strategies = Column(ARRAY(String))
    period = Column(String(20))
    interval = Column(String(10))
    created_at = Column(DateTime, server_default=func.now())

    results = relationship("ComparisonResult", back_populates="comparison")


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comparison_id = Column(String(50), ForeignKey("strategy_comparisons.comparison_id"))
    strategy = Column(String(50), nullable=False)
    ticker = Column(String(20), nullable=False)

    # Metrics for comparison
    return_pct = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    profit_factor = Column(Float)

    comparison = relationship("StrategyComparison", back_populates="results")
```

#### Risk Analytics Models

```python
# Risk Analytics
class RiskMetrics(Base):
    __tablename__ = "risk_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_id = Column(Integer, ForeignKey("backtest_stats.id"))
    var_95 = Column(Float)  # Value at Risk 95%
    var_99 = Column(Float)  # Value at Risk 99%
    cvar_95 = Column(Float)  # Conditional VaR
    beta = Column(Float)
    alpha = Column(Float)
    information_ratio = Column(Float)
    tail_ratio = Column(Float)
    common_sense_ratio = Column(Float)
```

#### ML Model Metadata

```python
# ML Model Metadata
class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    model_type = Column(String(50), nullable=False)  # LSTM, RF, XGBOOST
    version = Column(String(20), nullable=False)
    features = Column(ARRAY(String))
    target = Column(String(50))
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
```

#### Monitoring Models

```python
# Monitoring Alerts
class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)  # STRATEGY_DEGRADATION, API_HEALTH, etc.
    severity = Column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    message = Column(Text, nullable=False)
    metadata = Column(JSONB)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)
```

---

## 1.2 New Repository Layer

### File: `app/db/repository.py` (Additions)

```python
from sqlalchemy.orm import selectinload

# ---------------------------------------------------------------------------
# PortfolioRepository
# ---------------------------------------------------------------------------

class PortfolioRepository:
    async def create(self, portfolio: Portfolio) -> Portfolio:
        async with AsyncSessionLocal() as session:
            session.add(portfolio)
            await session.commit()
            await session.refresh(portfolio)
            return portfolio

    async def get_by_user(self, user_id: str) -> list[Portfolio]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Portfolio).where(Portfolio.user_id == user_id)
            )
            return result.scalars().all()

    async def get_with_allocations(self, portfolio_id: int) -> Portfolio | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Portfolio)
                .options(selectinload(Portfolio.allocations))
                .where(Portfolio.id == portfolio_id)
            )
            return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# PaperTradeRepository
# ---------------------------------------------------------------------------

class PaperTradeRepository:
    async def create(self, trade: PaperTrade) -> PaperTrade:
        async with AsyncSessionLocal() as session:
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade

    async def get_open_trades(self, portfolio_id: int) -> list[PaperTrade]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PaperTrade).where(
                    PaperTrade.portfolio_id == portfolio_id,
                    PaperTrade.status == "OPEN"
                )
            )
            return result.scalars().all()

    async def close_trade(self, trade_id: int, exit_price: float) -> PaperTrade | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PaperTrade).where(PaperTrade.id == trade_id)
            )
            trade = result.scalar_one_or_none()
            if trade:
                trade.exit_price = exit_price
                trade.exit_time = datetime.now(UTC)
                trade.status = "CLOSED"
                trade.pnl = (exit_price - trade.entry_price) * trade.quantity
                trade.pnl_percentage = (exit_price / trade.entry_price - 1) * 100
                await session.commit()
                await session.refresh(trade)
            return trade


# ---------------------------------------------------------------------------
# StrategyComparisonRepository
# ---------------------------------------------------------------------------

class StrategyComparisonRepository:
    async def create(self, comparison: StrategyComparison) -> StrategyComparison:
        async with AsyncSessionLocal() as session:
            session.add(comparison)
            await session.commit()
            await session.refresh(comparison)
            return comparison

    async def get_with_results(self, comparison_id: str) -> StrategyComparison | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(StrategyComparison)
                .options(selectinload(StrategyComparison.results))
                .where(StrategyComparison.comparison_id == comparison_id)
            )
            return result.scalar_one_or_none()
```

---

## 1.3 Database Migration Plan

### Required SQL Migrations

```sql
-- Portfolios
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    initial_capital FLOAT NOT NULL,
    current_capital FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE portfolio_allocations (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    weight FLOAT NOT NULL,
    position_size FLOAT NOT NULL
);

-- Paper Trading
CREATE TABLE paper_trades (
    id BIGINT PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    action VARCHAR(10) NOT NULL,
    entry_price FLOAT,
    exit_price FLOAT,
    quantity FLOAT NOT NULL,
    status VARCHAR(20) DEFAULT 'OPEN',
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    pnl FLOAT,
    pnl_percentage FLOAT
);

-- Strategy Comparison
CREATE TABLE strategy_comparisons (
    id SERIAL PRIMARY KEY,
    comparison_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    tickers TEXT[],
    strategies TEXT[],
    period VARCHAR(20),
    interval VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE comparison_results (
    id SERIAL PRIMARY KEY,
    comparison_id VARCHAR(50) REFERENCES strategy_comparisons(comparison_id),
    strategy VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    return_pct FLOAT,
    sharpe_ratio FLOAT,
    max_drawdown FLOAT,
    win_rate FLOAT,
    profit_factor FLOAT
);

-- Risk Metrics
CREATE TABLE risk_metrics (
    id SERIAL PRIMARY KEY,
    backtest_id INTEGER REFERENCES backtest_stats(id),
    var_95 FLOAT,
    var_99 FLOAT,
    cvar_95 FLOAT,
    beta FLOAT,
    alpha FLOAT,
    information_ratio FLOAT,
    tail_ratio FLOAT,
    common_sense_ratio FLOAT
);

-- ML Models
CREATE TABLE ml_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    features TEXT[],
    target VARCHAR(50),
    accuracy FLOAT,
    precision FLOAT,
    recall FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- System Alerts
CREATE TABLE system_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'INFO',
    message TEXT NOT NULL,
    metadata JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
```

---

## 1.4 Checklist

- [ ] Add new models to `app/db/models.py`
- [ ] Add new repositories to `app/db/repository.py`
- [ ] Create database migration script
- [ ] Run migrations in development environment
- [ ] Test basic CRUD operations for new models
- [ ] Update existing imports to include new models

---

## 1.5 Dependencies

None - this phase uses existing dependencies.

---

**Next Phase:** [Phase 2: Trading Accuracy](./phase-2-trading-accuracy.md)
