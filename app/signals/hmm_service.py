"""
Service layer for HMM Market Regime Analysis.

Handles business logic for fetching market data and calculating HMM regime
probabilities.  Returns a structured response ready for the API router.
"""

from collections import defaultdict

from starlette.status import HTTP_200_OK

from app.signals.hmm_dto import (
    DominantRegime,
    HMMRegimeDataPoint,
    HMMRegimeStats,
    HMMRegimeSummary,
    HMMResponseDTO,
    HMMTransitionEvent,
)
from app.signals.signals_generator.hmm_signals import calculate_hmm_regime
from app.signals.utils.yfinance import getYFinanceDataAsync

# Confidence level thresholds (0-100 probability scale, applied to max filtered prob)
_CONFIDENCE_HIGH = 70.0
_CONFIDENCE_MEDIUM = 50.0


# Per-interval HMM stability defaults.
#
# Design rationale (two axes):
#   • p_stay: prior stickiness per bar. A bar on a 1m chart is almost pure noise,
#     so the filter needs a very strong prior (0.97) to smooth it. A bar on a 1d
#     chart carries genuine information, so a low prior (0.68) lets the filter
#     respond quickly. The filter's "relaxation time" ≈ 1/(1−p_stay) bars, meaning
#     p_stay=0.97 takes ~33 bars to fully absorb a reversal; p_stay=0.68 takes ~3.
#   • min_dwell + switch_margin: hard hysteresis gate on top of the filter.
#     Short intervals need aggressive gates (1m: 30 bars = 30 min, 30 pp margin) to
#     block residual noise that survives the filter. Long intervals need permissive
#     gates (1d: 2 bars = 2 days, 5 pp margin) so genuine trend reversals are not
#     delayed by an overly strict gate.
def _row(bull: float, bear: float, chop: float, dwell: int, margin: float) -> dict:
    return {
        "p_stay_bull": bull,
        "p_stay_bear": bear,
        "p_stay_chop": chop,
        "min_dwell": dwell,
        "switch_margin": margin,
    }


_INTERVAL_DEFAULTS: dict[str, dict] = {
    "1m": _row(0.97, 0.97, 0.88, 30, 30.0),
    "2m": _row(0.96, 0.96, 0.86, 20, 28.0),
    "5m": _row(0.95, 0.95, 0.84, 15, 28.0),
    "15m": _row(0.94, 0.94, 0.82, 10, 26.0),
    "30m": _row(0.93, 0.93, 0.80, 8, 24.0),
    "60m": _row(0.92, 0.92, 0.78, 10, 22.0),
    "90m": _row(0.91, 0.91, 0.77, 8, 20.0),
    "1h": _row(0.92, 0.92, 0.78, 10, 22.0),
    "2h": _row(0.90, 0.90, 0.76, 6, 18.0),
    "4h": _row(0.80, 0.80, 0.66, 3, 8.0),
    "1d": _row(0.68, 0.68, 0.56, 2, 5.0),
    "5d": _row(0.62, 0.62, 0.52, 1, 4.0),
    "1wk": _row(0.58, 0.58, 0.48, 1, 3.0),
    "1mo": _row(0.55, 0.55, 0.45, 1, 2.0),
}
_FALLBACK_DEFAULTS: dict = {
    "p_stay_bull": 0.85,
    "p_stay_bear": 0.85,
    "p_stay_chop": 0.70,
    "min_dwell": 3,
    "switch_margin": 12.0,
}


def _effective_params(
    interval: str,
    p_stay_bull: float | None,
    p_stay_bear: float | None,
    p_stay_chop: float | None,
    min_dwell: int | None,
    switch_margin: float | None,
) -> dict:
    """Resolve HMM stability params: use user-supplied value or auto-scale from interval."""
    auto = _INTERVAL_DEFAULTS.get(interval, _FALLBACK_DEFAULTS)
    return {
        "p_stay_bull": p_stay_bull if p_stay_bull is not None else auto["p_stay_bull"],
        "p_stay_bear": p_stay_bear if p_stay_bear is not None else auto["p_stay_bear"],
        "p_stay_chop": p_stay_chop if p_stay_chop is not None else auto["p_stay_chop"],
        "min_dwell": min_dwell if min_dwell is not None else auto["min_dwell"],
        "switch_margin": switch_margin if switch_margin is not None else auto["switch_margin"],
    }


async def get_hmm_regime_data(
    ticker: str,
    interval: str = "1d",
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    length: int = 20,
    p_stay_bull: float | None = None,
    p_stay_bear: float | None = None,
    p_stay_chop: float | None = None,
    adaptive: bool = True,
    min_dwell: int | None = None,
    switch_margin: float | None = None,
) -> HMMResponseDTO:
    """
    Fetch market data and calculate HMM regime probabilities.

    When p_stay_*, min_dwell, or switch_margin are None (the default), values are
    auto-scaled for the requested interval — e.g. 1h gets higher min_dwell and
    switch_margin to prevent whipsaw, while 4h gets lower values so recoveries from
    bear are detected promptly.

    Args:
        ticker: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
        interval: Data interval ('1d', '1h', '4h', etc.)
        period: Time period (e.g., '365d')
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        length: Lookback period for observable calculations
        p_stay_bull: P(Bull→Bull); None = auto-scaled.
        p_stay_bear: P(Bear→Bear); None = auto-scaled.
        p_stay_chop: P(Chop→Chop); None = auto-scaled.
        adaptive: Calibrate emissions from data via GaussianMixture when True
        min_dwell: Min bars to hold a regime before switching; None = auto-scaled.
        switch_margin: Min probability lead (pp) to switch; None = auto-scaled.

    Returns:
        HMMResponseDTO with regime probabilities, smoothed history, transition
        events, per-regime statistics, and summary.

    Raises:
        ValueError: If data fetching fails or HMM calculation fails.
    """
    if period is None and start is None:
        period = "365d"

    try:
        df = await getYFinanceDataAsync(
            ticker=ticker,
            interval=interval,
            period=period,
            start=start,
            end=end,
        )
    except Exception as e:
        raise ValueError(f"Failed to fetch data for {ticker}: {e}") from e

    if df is None or len(df) == 0:
        raise ValueError(f"No data available for ticker {ticker} with given parameters")

    params = _effective_params(
        interval, p_stay_bull, p_stay_bear, p_stay_chop, min_dwell, switch_margin
    )

    try:
        df = calculate_hmm_regime(
            df=df,
            length=length,
            adaptive=adaptive,
            **params,
        )
    except Exception as e:
        raise ValueError(f"HMM calculation failed: {e}") from e

    # ---- Convert DataFrame rows → data points ----
    timestamps = list(df.index)
    regime_data: list[HMMRegimeDataPoint] = []

    for i, (timestamp, row) in enumerate(df.iterrows()):
        bars_in = int(row["bars_in_regime"])
        start_idx = max(0, i - bars_in + 1)
        regime_start_ts = timestamps[start_idx].isoformat()

        regime_data.append(
            HMMRegimeDataPoint(
                timestamp=timestamp.isoformat(),
                close=float(row["Close"]),
                obs_momentum=float(row["obs_momentum"]),
                obs_volatility=float(row["obs_volatility"]),
                obs_rsi=float(row["obs_rsi"]),
                # Causal filtered
                prob_bull=float(row["prob_bull"]),
                prob_bear=float(row["prob_bear"]),
                prob_chop=float(row["prob_chop"]),
                # Smoothed
                prob_bull_smoothed=float(row["prob_bull_smoothed"]),
                prob_bear_smoothed=float(row["prob_bear_smoothed"]),
                prob_chop_smoothed=float(row["prob_chop_smoothed"]),
                # Regime label
                dominant_regime=DominantRegime(str(row["regime"])),
                regime_state=int(row["regime_state"]),
                # Confidence
                confidence_score=float(row["confidence"]),
                confidence_entropy=float(row["confidence_entropy"]),
                confidence_margin=float(row["confidence_margin"]),
                # Duration
                bars_in_regime=bars_in,
                regime_start=regime_start_ts,
            )
        )

    if not regime_data:
        raise ValueError(f"No regime data points produced for {ticker}")

    # ---- Build transition events ----
    transition_events: list[HMMTransitionEvent] = []
    for i in range(1, len(regime_data)):
        prev = regime_data[i - 1]
        curr = regime_data[i]
        if curr.dominant_regime != prev.dominant_regime:
            transition_events.append(
                HMMTransitionEvent(
                    timestamp=curr.timestamp,
                    from_regime=prev.dominant_regime,
                    to_regime=curr.dominant_regime,
                    confidence_score=curr.confidence_score,
                    bars_in_prev_regime=prev.bars_in_regime,
                )
            )

    # ---- Per-regime statistics ----
    span_durations: dict[DominantRegime, list[int]] = defaultdict(list)
    if regime_data:
        current_regime = regime_data[0].dominant_regime
        span_start = 0
        for i, point in enumerate(regime_data):
            if point.dominant_regime != current_regime:
                span_durations[current_regime].append(i - span_start)
                current_regime = point.dominant_regime
                span_start = i
        span_durations[current_regime].append(len(regime_data) - span_start)

    total_bars = len(regime_data)
    regime_statistics: list[HMMRegimeStats] = []
    for regime in DominantRegime:
        durations = span_durations.get(regime, [])
        regime_total = sum(durations)
        count = len(durations)
        avg_duration = regime_total / count if count > 0 else 0.0
        regime_statistics.append(
            HMMRegimeStats(
                regime=regime,
                count=count,
                total_bars=regime_total,
                avg_duration=avg_duration,
                pct_time=regime_total / total_bars * 100 if total_bars > 0 else 0.0,
            )
        )

    # ---- Summary (latest bar) ----
    latest = regime_data[-1]

    if latest.confidence_score > _CONFIDENCE_HIGH:
        confidence_level = "HIGH"
    elif latest.confidence_score > _CONFIDENCE_MEDIUM:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    strategy_map = {
        DominantRegime.BULL: "Trend Following (Long)",
        DominantRegime.BEAR: "Trend Following (Short)",
        DominantRegime.CHOP: "Mean Reversion or Stay Out",
    }

    summary = HMMRegimeSummary(
        current_regime=latest.dominant_regime,
        current_state=latest.regime_state,
        confidence=confidence_level,
        confidence_score=latest.confidence_score,
        confidence_entropy=latest.confidence_entropy,
        confidence_margin=latest.confidence_margin,
        prob_bull=latest.prob_bull,
        prob_bear=latest.prob_bear,
        prob_chop=latest.prob_chop,
        recommended_strategy=strategy_map[latest.dominant_regime],
        bars_in_current_regime=latest.bars_in_regime,
        current_regime_start=latest.regime_start,
    )

    return HMMResponseDTO(
        status=HTTP_200_OK,
        message=f"HMM regime data for {ticker}",
        data=regime_data,
        summary=summary,
        transition_events=transition_events,
        regime_statistics=regime_statistics,
        ticker=ticker,
        interval=interval,
        data_points=len(regime_data),
    )
