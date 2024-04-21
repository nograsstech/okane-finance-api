from fastapi import APIRouter, Depends, BackgroundTasks
from dotenv import load_dotenv
from app.signals.dto import SignalRequestDTO, SignalResponseDTO, BacktestResponseDTO, BacktestProcessResponseDTO
from app.signals import service
from starlette.status import HTTP_200_OK
from app.auth.basic_auth import get_current_username
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

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
    username: Annotated[str, Depends(get_current_username)], params: SignalRequestDTO = Depends()
) -> SignalResponseDTO:

    print("RUNNING IN FASTAPI")
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
    background_tasks: BackgroundTasks, params: SignalRequestDTO = Depends()
) -> BacktestProcessResponseDTO:  
    backtest_process_uuid = uuid.uuid4()
    
    # Save the UUID as a new entry in the trade actions database and return the UUID
    
    def execute_backtest():
        service.get_backtest_result(
            ticker=params.ticker,
            interval=params.interval,
            period=params.period,
            strategy=params.strategy,
            parameters=params.parameters,
            start=params.start,
            end=params.end,
            strategy_id=params.strategy_id,
            backtest_process_uuid=params.backtest_process_uuid
        )

    background_tasks.add_task(
        run_in_executor,
        execute_backtest
    )
    return str(backtest_process_uuid)

@router.get("/backtest/sync", status_code=HTTP_200_OK, response_model=BacktestResponseDTO)
async def backtest(
    background_tasks: BackgroundTasks, params: SignalRequestDTO = Depends()
) -> BacktestResponseDTO:  
    
    # Save the UUID as a new entry in the trade actions database and return the UUID
    
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
        
    return execute_backtest()
