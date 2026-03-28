"""
Data Transfer Objects (DTOs) for HMM Market Regime Analysis API.
"""

from enum import Enum

from pydantic import BaseModel, Field


class DominantRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    CHOP = "chop"


class HMMRequestDTO(BaseModel):
    """Request model for HMM regime analysis endpoint."""

    ticker: str = Field(..., description="Ticker symbol (e.g., 'AAPL', 'BTC-USD')")
    period: str | None = Field(
        None,
        description="Time period (e.g., '365d', '90d'). If not provided, uses default period from yfinance",
    )
    interval: str = Field(
        default="1d",
        description="Data interval: '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo'",
    )
    start: str | None = Field(None, description="Start date (YYYY-MM-DD format)")
    end: str | None = Field(None, description="End date (YYYY-MM-DD format)")
    length: int = Field(
        default=20,
        ge=5,
        description="Lookback period for observable calculations",
    )
    p_stay_bull: float = Field(
        default=0.75,
        ge=0.0,
        le=0.99,
        description="Probability of staying in bull regime",
    )
    p_stay_bear: float = Field(
        default=0.75,
        ge=0.0,
        le=0.99,
        description="Probability of staying in bear regime",
    )
    p_stay_chop: float = Field(
        default=0.55,
        ge=0.0,
        le=0.99,
        description="Probability of staying in chop regime",
    )


class HMMRegimeDataPoint(BaseModel):
    """Single data point representing regime probabilities at a timestamp."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    close: float = Field(..., description="Close price")
    obs_momentum: float = Field(..., description="Standardized momentum observable")
    obs_volatility: float = Field(..., description="Standardized volatility observable")
    obs_rsi: float = Field(..., description="Standardized RSI observable (centered at 50)")
    prob_bull: float = Field(..., ge=0, le=100, description="Bull regime probability (0-100)")
    prob_bear: float = Field(..., ge=0, le=100, description="Bear regime probability (0-100)")
    prob_chop: float = Field(..., ge=0, le=100, description="Chop regime probability (0-100)")
    dominant_regime: DominantRegime = Field(..., description="Dominant regime")
    confidence_score: float = Field(..., ge=0, le=100, description="Confidence score (max probability)")
    regime_state: int = Field(..., description="Regime state: 1 (bull), -1 (bear), 0 (chop)")


class HMMRegimeSummary(BaseModel):
    """Summary of current/latest regime state."""

    current_regime: DominantRegime = Field(..., description="Current dominant regime")
    current_state: int = Field(..., description="Current regime state code")
    confidence: str = Field(..., description="Confidence level: 'HIGH', 'MEDIUM', or 'LOW'")
    confidence_score: float = Field(..., description="Current confidence score")
    prob_bull: float = Field(..., description="Current bull probability")
    prob_bear: float = Field(..., description="Current bear probability")
    prob_chop: float = Field(..., description="Current chop probability")
    recommended_strategy: str = Field(..., description="Recommended trading strategy")


class HMMResponseDTO(BaseModel):
    """Response model for HMM regime analysis endpoint."""

    status: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Response message")
    data: list[HMMRegimeDataPoint] = Field(..., description="Time series of regime probabilities")
    summary: HMMRegimeSummary = Field(..., description="Summary of current regime state")
    ticker: str = Field(..., description="Ticker symbol")
    interval: str = Field(..., description="Data interval used")
    data_points: int = Field(..., description="Number of data points returned")
