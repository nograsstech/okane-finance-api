"""
Data Transfer Objects (DTOs) for HMM Market Regime Analysis API.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class DominantRegime(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    CHOP = "chop"


class HMMRequestDTO(BaseModel):
    """Request model for HMM regime analysis endpoint."""

    ticker: str = Field(..., description="Ticker symbol (e.g., 'AAPL', 'BTC-USD')")
    period: str | None = Field(
        None,
        description=(
            "Time period (e.g., '365d', '90d'). "
            "If not provided, uses default period from yfinance."
        ),
    )
    interval: str = Field(
        default="1d",
        description=(
            "Data interval: '1m', '2m', '5m', '15m', '30m', "
            "'60m', '90m', '1h', '1d', '5d', '1wk', '1mo'"
        ),
    )
    start: str | None = Field(None, description="Start date (YYYY-MM-DD format)")
    end: str | None = Field(None, description="End date (YYYY-MM-DD format)")
    length: int = Field(
        default=20,
        ge=5,
        description="Lookback period for observable calculations",
    )
    p_stay_bull: float | None = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="P(Bull→Bull) transition; None = auto-scale for the interval.",
    )
    p_stay_bear: float | None = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="P(Bear→Bear) transition; None = auto-scale for the interval.",
    )
    p_stay_chop: float | None = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="P(Chop→Chop) transition; None = auto-scale for the interval.",
    )
    adaptive: bool = Field(
        default=True,
        description=(
            "If True, calibrate emission parameters from the data via GaussianMixture. "
            "Falls back to fixed regime params if calibration fails. "
            "Set False for strictly fixed, non-look-ahead emissions."
        ),
    )
    min_dwell: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Minimum bars to hold a regime before it can switch. "
            "None = auto-scale for the interval (e.g. 8 bars on 1h, 4 on 4h)."
        ),
    )
    switch_margin: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Minimum probability lead (pp) the new regime must have to trigger a switch. "
            "None = auto-scale for the interval (e.g. 20 pp on 1h, 10 pp on 4h)."
        ),
    )


class HMMRegimeDataPoint(BaseModel):
    """Single data point representing regime probabilities at a timestamp."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    close: float = Field(..., description="Close price")

    # Observables
    obs_momentum: float = Field(..., description="Standardized momentum observable")
    obs_volatility: float = Field(..., description="Standardized volatility observable")
    obs_rsi: float = Field(..., description="Standardized RSI observable (centered at 50)")

    # Causal filtered probabilities (never revised by future bars)
    prob_bull: float = Field(..., ge=0, le=100, description="Bull prob — causal filtered (0-100)")
    prob_bear: float = Field(..., ge=0, le=100, description="Bear prob — causal filtered (0-100)")
    prob_chop: float = Field(..., ge=0, le=100, description="Chop prob — causal filtered (0-100)")

    # Forward-backward smoothed probabilities (more accurate for historical display)
    prob_bull_smoothed: float = Field(
        ..., ge=0, le=100, description="Bull prob — forward-backward smoothed (0-100)"
    )
    prob_bear_smoothed: float = Field(
        ..., ge=0, le=100, description="Bear prob — forward-backward smoothed (0-100)"
    )
    prob_chop_smoothed: float = Field(
        ..., ge=0, le=100, description="Chop prob — forward-backward smoothed (0-100)"
    )

    # Regime label (derived from smoothed + hysteresis; last bar overridden by filtered)
    dominant_regime: DominantRegime = Field(..., description="Dominant regime")
    regime_state: int = Field(..., description="Regime state: 1 (bull), -1 (bear), 0 (chop)")

    # Confidence metrics
    confidence_score: float = Field(
        ..., ge=0, le=100, description="Confidence — max filtered probability (0-100)"
    )
    confidence_entropy: float = Field(
        ..., ge=0, le=100,
        description="Entropy confidence: (1 - H/log3)*100; 100=certain, 0=uncertain",
    )
    confidence_margin: float = Field(
        ..., ge=0, le=100,
        description="Margin: top-1 minus top-2 filtered probability (pp)",
    )

    # Regime duration
    bars_in_regime: int = Field(..., ge=1, description="Bars continuously in the current regime")
    regime_start: str = Field(
        ..., description="ISO 8601 timestamp of the current regime's start bar"
    )


class HMMTransitionEvent(BaseModel):
    """A single regime-change event in the time series."""

    timestamp: str = Field(..., description="ISO 8601 timestamp of the regime change")
    from_regime: DominantRegime = Field(..., description="Regime before the change")
    to_regime: DominantRegime = Field(..., description="Regime after the change")
    confidence_score: float = Field(..., ge=0, le=100, description="Confidence at transition bar")
    bars_in_prev_regime: int = Field(
        ..., ge=1, description="Duration of the preceding regime span (bars)"
    )


class HMMRegimeStats(BaseModel):
    """Per-regime aggregate statistics for the full time series."""

    regime: DominantRegime = Field(..., description="Regime label")
    count: int = Field(..., ge=0, description="Number of distinct regime spans")
    total_bars: int = Field(..., ge=0, description="Total bars spent in this regime")
    avg_duration: float = Field(..., ge=0, description="Average span duration (bars)")
    pct_time: float = Field(
        ..., ge=0, le=100, description="Percentage of total bars in this regime"
    )


class HMMRegimeSummary(BaseModel):
    """Summary of current/latest regime state."""

    current_regime: DominantRegime = Field(..., description="Current dominant regime")
    current_state: int = Field(..., description="Current regime state code")
    confidence: str = Field(..., description="Confidence level: 'HIGH', 'MEDIUM', or 'LOW'")
    confidence_score: float = Field(..., description="Current confidence score (max filtered prob)")
    confidence_entropy: float = Field(..., description="Current entropy-based confidence")
    confidence_margin: float = Field(..., description="Current probability margin (pp)")
    prob_bull: float = Field(..., description="Current bull probability (filtered)")
    prob_bear: float = Field(..., description="Current bear probability (filtered)")
    prob_chop: float = Field(..., description="Current chop probability (filtered)")
    recommended_strategy: str = Field(..., description="Recommended trading strategy")
    bars_in_current_regime: int = Field(..., ge=1, description="Bars in the current regime")
    current_regime_start: str = Field(..., description="ISO 8601 timestamp of current regime start")


class HMMResponseDTO(BaseModel):
    """Response model for HMM regime analysis endpoint."""

    status: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Response message")
    data: list[HMMRegimeDataPoint] = Field(..., description="Time series of regime probabilities")
    summary: HMMRegimeSummary = Field(..., description="Summary of current regime state")
    transition_events: list[HMMTransitionEvent] = Field(..., description="Regime-change events")
    regime_statistics: list[HMMRegimeStats] = Field(..., description="Per-regime aggregate stats")
    ticker: str = Field(..., description="Ticker symbol")
    interval: str = Field(..., description="Data interval used")
    data_points: int = Field(..., description="Number of data points returned")
