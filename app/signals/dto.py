from pydantic import BaseModel, Field
from typing import Any

class SignalRequestDTO(BaseModel):
    ticker: str = Field(...)
    period: str = Field(None)
    interval: str = Field(...)
    strategy: str = Field(None)
    parameters: str = Field(None)
    start: str = Field(None)
    end: str = Field(None)
    
    
class SignalResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    
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
    
class BacktestResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
    data: BacktestStats = Field(...)
