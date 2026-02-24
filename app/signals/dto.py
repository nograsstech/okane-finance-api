from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.signals.strategies.strategy_list import strategy_list


class SignalRequestDTO(BaseModel):
    ticker: str = Field(...)
    period: str | None = Field(None)
    interval: str = Field(...)
    strategy: Literal[tuple(strategy_list)] | None = Field(None, allowed_values=strategy_list)  # type: ignore
    parameters: str | None = Field(None)
    start: str | None = Field(None)
    end: str | None = Field(None)
    strategy_id: str | None = Field(None)
    backtest_process_uuid: str | None = Field(None)


class Signal(BaseModel):
    gmtTime: str = Field(...)
    Open: float = (Field(...),)
    High: float = (Field(...),)
    Low: float = (Field(...),)
    Close: float = (Field(...),)
    Volume: float = (Field(...),)
    TotalSignal: float = (Field(...),)


class SignalsDict(BaseModel):
    latest_signal: Signal = Field(...)
    all_signals: list[Signal] = Field(...)


class SignalRequestData(BaseModel):
    ticker: str
    period: str
    interval: str
    strategy: str
    signals: SignalsDict


class SignalResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: SignalRequestData = Field(...)


class BacktestStats(BaseModel):
    ticker: Any
    max_drawdown_percentage: float
    start_time: Any
    end_time: Any
    duration: Any
    exposure_time_percentage: float
    final_equity: float
    peak_equity: float
    return_percentage: float
    buy_and_hold_return: float
    return_annualized: float
    volatility_annualized: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    average_drawdown_percentage: float
    max_drawdown_duration: Any
    average_drawdown_duration: Any
    trade_count: int
    win_rate: float
    best_trade: float
    worst_trade: float
    avg_trade: float
    max_trade_duration: Any
    average_trade_duration: Any
    profit_factor: float
    html: Any
    tpslRatio: float
    sl_coef: float


class BacktestResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: BacktestStats = Field(...)


class BacktestProcessResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: str = Field(...)


class TradeAction(BaseModel):
    backtest_id: int = Field(...)
    datetime: str = Field(...)
    trade_action: str = Field(...)
    entry_price: float = Field(...)
    price: float = Field(...)
    sl: float = Field(...)
    tp: float = Field(...)
    size: float = Field(...)


class BacktestReplayRequestDTO(BaseModel):
    backtest_id: int = Field(..., description="The ID of the backtest to replay")


class BacktestReplayResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: BacktestStats = Field(...)


class StrategyInfo(BaseModel):
    """Information about a single trading strategy."""

    id: str = Field(..., description="Unique identifier for the strategy")
    name: str = Field(..., description="Display name of the strategy")
    description: str | None = Field(None, description="Optional description of the strategy")


class StrategyListResponseDTO(BaseModel):
    """Response model for the strategy list endpoint."""

    status: int = Field(...)
    message: str = Field(...)
    data: list[StrategyInfo] = Field(...)
