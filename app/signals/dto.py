from pydantic import BaseModel, Field
from typing import Optional

class SignalRequestDTO(BaseModel):
    ticker: str = Field(...)
    period: str | None = Field(None)
    interval: str = Field(...)
    strategy: str | None = Field(None)
    parameters: str | None = Field(None)
    start: str | None = Field(None)
    end: str | None = Field(None)
    
    
class SignalResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    
class BacktestStats(BaseModel):
    max_drawdown_percentage: Optional[float]
    start: Optional[str]
    end: Optional[str]
    duration: Optional[str]
    exposure_time_percentage: Optional[float]
    final_equity: Optional[float]
    peak_equity: Optional[float]
    return_: Optional[float] = Field(alias="return")
    buy_and_hold_return: Optional[float]
    return_annualized: Optional[float]
    volatility_annualized: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    average_drawdown_percentage: Optional[float]
    max_drawdown_duration: Optional[str]
    average_drawdown_duration: Optional[str]
    trade_count: Optional[int]
    win_rate: Optional[float]
    best_trade: Optional[float]
    worst_trade: Optional[float]
    avg_trade: Optional[float]
    max_trade_duration: Optional[str]
    average_trade_duration: Optional[str]
    profit_factor: Optional[float]
    
class BacktestResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: dict = Field({
        "ticker": str,
        "stats": BacktestStats,
        "html": str
    })
