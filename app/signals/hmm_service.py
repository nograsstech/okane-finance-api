"""
Service layer for HMM Market Regime Analysis.

Handles business logic for fetching market data and calculating HMM regime probabilities.
"""

from starlette.status import HTTP_200_OK

# Confidence level thresholds (0-100 probability scale)
_CONFIDENCE_HIGH = 70.0
_CONFIDENCE_MEDIUM = 50.0

from app.signals.signals_generator.hmm_signals import calculate_hmm_regime
from app.signals.utils.yfinance import getYFinanceDataAsync
from app.signals.hmm_dto import (
    DominantRegime,
    HMMRegimeDataPoint,
    HMMRegimeSummary,
    HMMResponseDTO,
)


async def get_hmm_regime_data(
    ticker: str,
    interval: str = "1d",
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    length: int = 20,
    p_stay_bull: float = 0.80,
    p_stay_bear: float = 0.80,
    p_stay_chop: float = 0.60,
) -> HMMResponseDTO:
    """
    Fetch market data and calculate HMM regime probabilities.

    Args:
        ticker: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
        interval: Data interval ('1d', '1h', etc.)
        period: Time period (e.g., '365d')
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        length: Lookback period for observable calculations
        p_stay_bull: Probability of staying in bull regime
        p_stay_bear: Probability of staying in bear regime
        p_stay_chop: Probability of staying in chop regime

    Returns:
        HMMResponseDTO with regime probabilities and summary

    Raises:
        ValueError: If data fetching fails or HMM calculation fails
    """
    # Default period if not specified
    if period is None and start is None:
        period = "365d"  # Default to 1 year

    # Fetch OHLCV data
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

    # Calculate HMM regime probabilities
    try:
        df = calculate_hmm_regime(
            df=df,
            length=length,
            p_stay_bull=p_stay_bull,
            p_stay_bear=p_stay_bear,
            p_stay_chop=p_stay_chop,
        )
    except Exception as e:
        raise ValueError(f"HMM calculation failed: {e}") from e

    # Convert DataFrame to list of data points
    regime_data = []
    for timestamp, row in df.iterrows():
        regime_data.append(
            HMMRegimeDataPoint(
                timestamp=timestamp.isoformat(),
                close=float(row['Close']),
                obs_momentum=float(row['obs_momentum']),
                obs_volatility=float(row['obs_volatility']),
                prob_bull=float(row['prob_bull']),
                prob_bear=float(row['prob_bear']),
                prob_chop=float(row['prob_chop']),
                dominant_regime=str(row['regime']),
                confidence_score=float(row['confidence']),
                regime_state=int(row['regime_state']),
            )
        )

    if not regime_data:
        raise ValueError(f"No regime data points produced for {ticker}")

    # Get latest (last) data point for summary
    latest = regime_data[-1]

    # Determine confidence level
    if latest.confidence_score > _CONFIDENCE_HIGH:
        confidence_level = "HIGH"
    elif latest.confidence_score > _CONFIDENCE_MEDIUM:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    # Determine recommended strategy
    strategy_map = {
        DominantRegime.BULL: 'Trend Following (Long)',
        DominantRegime.BEAR: 'Trend Following (Short)',
        DominantRegime.CHOP: 'Mean Reversion or Stay Out',
    }
    recommended_strategy = strategy_map[latest.dominant_regime]

    # Create summary
    summary = HMMRegimeSummary(
        current_regime=latest.dominant_regime,
        current_state=latest.regime_state,
        confidence=confidence_level,
        confidence_score=latest.confidence_score,
        prob_bull=latest.prob_bull,
        prob_bear=latest.prob_bear,
        prob_chop=latest.prob_chop,
        recommended_strategy=recommended_strategy,
    )

    # Create response
    return HMMResponseDTO(
        status=HTTP_200_OK,
        message=f"HMM regime data for {ticker}",
        data=regime_data,
        summary=summary,
        ticker=ticker,
        interval=interval,
        data_points=len(regime_data),
    )
