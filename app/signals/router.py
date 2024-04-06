from fastapi import APIRouter, Depends
from dotenv import load_dotenv
from app.signals.dto import SignalRequestDTO, SignalResponseDTO, BacktestResponseDTO
from app.signals import service
from starlette.status import HTTP_200_OK

router = APIRouter(
    prefix="/signals",
    tags=["signals"],
    responses={404: {"description": "Not found"}},
)


# Query parameters: ticker, start, end, interval, strategy, and parameters
@router.get("/", response_model=SignalResponseDTO, status_code=HTTP_200_OK)
async def get_signals(params: SignalRequestDTO = Depends()) -> SignalResponseDTO:
    
    data = await service.get_signals(
        ticker = params.ticker,
        interval = params.interval,
        period = params.period,
        strategy = params.strategy,
        parameters = params.parameters,
        start = params.start,
        end = params.end,
    )
    return data


@router.get("/backtest", response_model=BacktestResponseDTO, status_code=HTTP_200_OK)
async def backtest(params: SignalRequestDTO = Depends()) -> BacktestResponseDTO:
    data = await service.get_backtest_result(
        ticker = params.ticker,
        interval = params.interval,
        period = params.period,
        strategy = params.strategy,
        parameters = params.parameters,
        start = params.start,
        end = params.end,
    )
    return data
