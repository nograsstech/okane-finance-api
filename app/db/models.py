"""
SQLAlchemy ORM models mapping to the existing Postgres tables in Supabase.

Tables reflected:
  - backtest_stats
  - trade_actions
  - unique_strategies  (read-only view / table)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base

# ---------------------------------------------------------------------------
# backtest_stats
# ---------------------------------------------------------------------------


class BacktestStat(Base):
    __tablename__ = "backtest_stats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Core identifiers
    ticker: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Performance metrics
    return_percentage: Mapped[float | None] = mapped_column(Double, nullable=True)
    return_annualized: Mapped[float | None] = mapped_column(Double, nullable=True)
    buy_and_hold_return: Mapped[float | None] = mapped_column(Double, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    volatility_annualized: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Equity
    final_equity: Mapped[float | None] = mapped_column(Double, nullable=True)
    peak_equity: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Drawdown
    max_drawdown_percentage: Mapped[float | None] = mapped_column(Double, nullable=True)
    average_drawdown_percentage: Mapped[float | None] = mapped_column(Double, nullable=True)
    max_drawdown_duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_drawdown_duration: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trade stats
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Double, nullable=True)
    best_trade: Mapped[float | None] = mapped_column(Double, nullable=True)
    worst_trade: Mapped[float | None] = mapped_column(Double, nullable=True)
    avg_trade: Mapped[float | None] = mapped_column(Double, nullable=True)
    max_trade_duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_trade_duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Double, nullable=True)
    exposure_time_percentage: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Duration
    start_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Strategy params
    tpsl_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    sl_coef: Mapped[float | None] = mapped_column(Double, nullable=True)
    tp_coef: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Notifications
    notifications_on: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # The backtest HTML (deflated + base64)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    last_optimized_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    # Relationship
    trade_actions: Mapped[list[TradeAction]] = relationship(
        "TradeAction", back_populates="backtest_stat", lazy="select"
    )


# ---------------------------------------------------------------------------
# trade_actions
# ---------------------------------------------------------------------------


class TradeAction(Base):
    __tablename__ = "trade_actions"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign key to backtest_stats
    backtest_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("backtest_stats.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Trade details
    datetime: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    trade_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Double, nullable=True)
    price: Mapped[float | None] = mapped_column(Double, nullable=True)
    sl: Mapped[float | None] = mapped_column(Double, nullable=True)
    tp: Mapped[float | None] = mapped_column(Double, nullable=True)
    size: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Relationship
    backtest_stat: Mapped[BacktestStat | None] = relationship(
        "BacktestStat", back_populates="trade_actions"
    )


# ---------------------------------------------------------------------------
# unique_strategies  (read-only view / table)
# ---------------------------------------------------------------------------


class UniqueStrategy(Base):
    __tablename__ = "unique_strategies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ticker: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval: Mapped[str | None] = mapped_column(Text, nullable=True)
    notifications_on: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_optimized_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    tpsl_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    sl_coef: Mapped[float | None] = mapped_column(Double, nullable=True)
    tp_coef: Mapped[float | None] = mapped_column(Double, nullable=True)
