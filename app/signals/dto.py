from __future__ import annotations

from datetime import date
from datetime import datetime as DateTime
from typing import Literal, cast

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator

from app.signals.strategies.strategy_list import strategy_list


class SignalRequestDTO(BaseModel):
    ticker: str = Field(...)
    period: str | None = Field(None)
    interval: str = Field(...)
    strategy: str | None = Field(
        None,
        json_schema_extra={"enum": cast(list[JsonValue], strategy_list)},
    )
    parameters: str | None = Field(None)
    start: str | None = Field(None)
    end: str | None = Field(None)
    strategy_id: str | None = Field(None)
    backtest_process_uuid: str | None = Field(None)
    skip_optimization: bool = Field(
        True,
        description="Skip parameter optimization unless an expensive optimization run is requested.",
    )

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, value: str | None) -> str | None:
        if value is not None and value not in strategy_list:
            raise ValueError(f"strategy must be one of: {', '.join(strategy_list)}")
        return value


class Signal(BaseModel):
    gmtTime: str = Field(...)
    Open: float = Field(...)
    High: float = Field(...)
    Low: float = Field(...)
    Close: float = Field(...)
    Volume: float = Field(...)
    TotalSignal: float = Field(...)


class SignalsDict(BaseModel):
    latest_signal: Signal = Field(...)
    all_signals: list[Signal] = Field(...)


class SignalRequestData(BaseModel):
    ticker: str
    period: str | None
    interval: str
    strategy: str | None
    signals: SignalsDict


class SignalResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: SignalRequestData = Field(...)


class BacktestStats(BaseModel):
    ticker: str
    max_drawdown_percentage: float
    start_time: str
    end_time: str
    duration: str
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
    max_drawdown_duration: str
    average_drawdown_duration: str
    trade_count: int
    win_rate: float
    best_trade: float
    worst_trade: float
    avg_trade: float
    max_trade_duration: str
    average_trade_duration: str
    profit_factor: float
    html: str
    tpslRatio: float
    sl_coef: float


class BacktestResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: BacktestStats = Field(...)


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


class PortfolioReplayRequestDTO(BaseModel):
    start_date: date
    end_date: date
    starting_equity: float = Field(gt=0, allow_inf_nan=False)
    risk_per_trade: float = Field(
        gt=0, allow_inf_nan=False, description="Fixed USD risk for each signal"
    )
    cost_per_trade: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_date_range(self) -> PortfolioReplayRequestDTO:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if (self.end_date - self.start_date).days > 59:
            raise ValueError("date range cannot exceed 59 days")
        return self


class PortfolioReplaySummaryDTO(BaseModel):
    starting_equity: float
    ending_equity: float
    net_pnl: float
    return_percentage: float
    realized_pnl: float
    unrealized_pnl: float
    total_costs: float
    max_drawdown: float
    max_drawdown_percentage: float
    total_trades: int
    closed_trades: int
    open_trades: int
    wins: int
    losses: int
    win_rate: float | None


class PortfolioEquityPointDTO(BaseModel):
    datetime: DateTime
    equity: float
    pnl: float


class PortfolioReplayTradeDTO(BaseModel):
    backtest_id: int
    ticker: str
    strategy: str
    datetime: DateTime
    action: str
    direction: Literal["long", "short"]
    entry_price: float
    exit_price: float | None
    stop_loss: float
    take_profit: float | None
    risk_units: float
    r_multiple: float | None
    pnl: float | None
    cost: float
    status: Literal["tp", "sl", "close", "marked", "skipped"]
    exit_datetime: DateTime | None
    message: str


class PortfolioStrategyResultDTO(BaseModel):
    backtest_id: int
    ticker: str
    strategy: str
    trades: int
    closed_trades: int
    open_trades: int
    wins: int
    net_pnl: float
    win_rate: float | None
    average_r: float | None


class PortfolioReplayDataDTO(BaseModel):
    start_date: date
    end_date: date
    summary: PortfolioReplaySummaryDTO
    enabled_strategy_count: int
    strategy_count_with_actions: int
    equity_curve: list[PortfolioEquityPointDTO]
    strategies: list[PortfolioStrategyResultDTO]
    trades: list[PortfolioReplayTradeDTO]
    warnings: list[str]


class PortfolioReplayResponseDTO(BaseModel):
    status: int
    message: str
    data: PortfolioReplayDataDTO


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
