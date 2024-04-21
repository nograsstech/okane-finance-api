from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, Union, List

class SignalRequestDTO(BaseModel):
    ticker: str = Field(...)
    period: Optional[str] = Field(None)
    interval: str = Field(...)
    strategy: Optional[str] = Field(None)
    parameters: Optional[str] = Field(None)
    start: Optional[str] = Field(None)
    end: Optional[str]= Field(None)
    strategy_id: Optional[str] = Field(None)
    backtest_process_uuid: Optional[str] = Field(None)
    
class Signal(BaseModel):
    gmtTime: str = Field(...)
    Open: float = Field(...),
    High: float = Field(...),
    Low: float = Field(...),
    Close: float = Field(...),
    Volume: float = Field(...),
    TotalSignal: float = Field(...),
    
class SignalsDict(BaseModel):
    latest_signal: Signal = Field(...)
    all_signals: List[Signal] = Field(...)
    
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
    
    