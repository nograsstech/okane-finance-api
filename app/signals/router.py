from fastapi import APIRouter, Depends, BackgroundTasks
from dotenv import load_dotenv
from app.signals.dto import SignalRequestDTO, SignalResponseDTO, BacktestResponseDTO
from app.signals import service
from starlette.status import HTTP_200_OK
from app.auth.basic_auth import get_current_username
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)

router = APIRouter(
    prefix="/signals",
    tags=["signals"],
    responses={404: {"description": "Not found"}},
)

def run_in_executor(func, *args, **kwargs):
    def wrapper():
        return func(*args, **kwargs)
    loop = asyncio.new_event_loop()
    return asyncio.ensure_future(loop.run_in_executor(executor, wrapper))


# Query parameters: ticker, start, end, interval, strategy, and parameters
@router.get("/", response_model=SignalResponseDTO, status_code=HTTP_200_OK)
async def get_signals(
    params: SignalRequestDTO = Depends(), username: str = Depends(get_current_username)
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


@router.get("/backtest", status_code=HTTP_200_OK) #response_model=BacktestResponseDTO
async def backtest(
    background_tasks: BackgroundTasks, params: SignalRequestDTO = Depends()
) : #-> BacktestResponseDTO
    myuuid = uuid.uuid4()
    
    def execute_backtest():
        service.get_backtest_result(
            ticker=params.ticker,
            interval=params.interval,
            period=params.period,
            strategy=params.strategy,
            parameters=params.parameters,
            start=params.start,
            end=params.end,
        )

    background_tasks.add_task(
        run_in_executor,
        execute_backtest
    )
    return myuuid
