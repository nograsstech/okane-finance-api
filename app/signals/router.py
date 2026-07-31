import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette.status import HTTP_200_OK

from app.auth.basic_auth import get_current_username
from app.signals import service
from app.signals.dto import (
    BacktestProcessResponseDTO,
    BacktestReplayRequestDTO,
    BacktestReplayResponseDTO,
    BacktestResponseDTO,
    PortfolioReplayRequestDTO,
    PortfolioReplayResponseDTO,
    SignalRequestDTO,
    SignalResponseDTO,
    StrategyListResponseDTO,
)
from app.signals.hmm_dto import HMMRequestDTO, HMMResponseDTO
from app.signals.hmm_service import get_hmm_regime_data
from app.signals.portfolio_replay import portfolio_replay

router = APIRouter(
    prefix="/signals",
    tags=["signals"],
    responses={404: {"description": "Not found"}},
)


# Query parameters: ticker, start, end, interval, strategy, and parameters
@router.get("/", response_model=SignalResponseDTO, status_code=HTTP_200_OK)
async def get_signals(
    username: Annotated[str, Depends(get_current_username)],
    params: SignalRequestDTO = Depends(),
) -> SignalResponseDTO:
    data = await service.get_signals(
        ticker=params.ticker,
        interval=params.interval,
        period=params.period,
        strategy=params.strategy,
        parameters=params.parameters,
        start=params.start,
        end=params.end,
    )
    return data


@router.get("/backtest", status_code=HTTP_200_OK, response_model=str)
async def backtest(
    username: Annotated[str, Depends(get_current_username)],
    background_tasks: BackgroundTasks,
    params: SignalRequestDTO = Depends(),
) -> BacktestProcessResponseDTO:
    backtest_process_uuid = uuid.uuid4()

    # Schedule the async work as a FastAPI background task
    background_tasks.add_task(
        service.get_backtest_result,
        ticker=params.ticker,
        interval=params.interval,
        period=params.period,
        strategy=params.strategy,
        parameters=params.parameters,
        start=params.start,
        end=params.end,
        strategy_id=params.strategy_id,
        backtest_process_uuid=params.backtest_process_uuid,
    )
    return str(backtest_process_uuid)


@router.get("/backtest/sync", status_code=HTTP_200_OK, response_model=BacktestResponseDTO)
async def backtest_sync(
    username: Annotated[str, Depends(get_current_username)],
    params: SignalRequestDTO = Depends(),
) -> BacktestResponseDTO:
    return await service.get_backtest_result(
        ticker=params.ticker,
        interval=params.interval,
        period=params.period,
        strategy=params.strategy,
        parameters=params.parameters,
        start=params.start,
        end=params.end,
    )


@router.get("/backtest/replay", status_code=HTTP_200_OK, response_model=BacktestReplayResponseDTO)
async def replay_backtest_endpoint(
    username: Annotated[str, Depends(get_current_username)],
    params: BacktestReplayRequestDTO = Depends(),
) -> BacktestReplayResponseDTO:
    """
    Replay a backtest from stored TradeAction records.

    Fetches fresh historical price data from yfinance and applies the stored trades
    to calculate backtest results. No caching - calculates on the fly.

    Args:
        backtest_id: The ID of the backtest to replay

    Returns:
        Full backtest stats and HTML report
    """
    return await service.replay_backtest(
        backtest_id=params.backtest_id,
    )


@router.post(
    "/portfolio-replay",
    status_code=HTTP_200_OK,
    response_model=PortfolioReplayResponseDTO,
)
async def portfolio_replay_endpoint(
    params: PortfolioReplayRequestDTO,
    username: Annotated[str, Depends(get_current_username)],
) -> PortfolioReplayResponseDTO:
    return await portfolio_replay(params)


@router.post("/strategy-notification-job", status_code=HTTP_200_OK)
async def strategy_notification(
    username: Annotated[str, Depends(get_current_username)],
) -> None:
    await service.strategy_notification_job()
    return None


@router.get("/strategies", status_code=HTTP_200_OK, response_model=StrategyListResponseDTO)
async def get_strategies(
    username: Annotated[str, Depends(get_current_username)],
) -> StrategyListResponseDTO:
    """
    Get the list of available trading strategies.

    Returns a list of all strategies that can be used for backtesting
    and signal generation.
    """
    return await service.get_strategies()


@router.get("/hmm/regimes", status_code=HTTP_200_OK, response_model=HMMResponseDTO)
async def get_hmm_regimes(
    username: Annotated[str, Depends(get_current_username)],
    params: HMMRequestDTO = Depends(),
) -> HMMResponseDTO:
    """
    Get Hidden Markov Model (HMM) market regime probabilities.

    Returns a time series of regime probabilities (Bull, Bear, Chop) for the given ticker.
    Uses a 3-state HMM with Bayesian updating, forward-backward smoothing, and
    hysteresis to produce an accurate, whipsaw-resistant regime timeline.

    Two probability streams are returned per bar:
    - prob_bull/bear/chop: causal filtered (never revised — safe for live signals)
    - prob_*_smoothed: forward-backward smoothed (accurate historical display)

    Response includes:
    - Full time series with filtered + smoothed probabilities, regime labels,
      duration info, and richer confidence metrics
    - transition_events: list of regime-change events with timestamps
    - regime_statistics: per-regime aggregate statistics
    - summary: current regime with recommended strategy

    Example:
        GET /signals/hmm/regimes?ticker=AAPL&period=365d&interval=1d
    """
    return await get_hmm_regime_data(
        ticker=params.ticker,
        interval=params.interval,
        period=params.period,
        start=params.start,
        end=params.end,
        length=params.length,
        p_stay_bull=params.p_stay_bull,
        p_stay_bear=params.p_stay_bear,
        p_stay_chop=params.p_stay_chop,
        adaptive=params.adaptive,
        min_dwell=params.min_dwell,
        switch_margin=params.switch_margin,
    )
