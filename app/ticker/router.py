from fastapi import APIRouter, Depends
from dotenv import load_dotenv
from app.ticker.dto import TickerRequestDTO, TickerResponseDTO
from app.ticker import service
from starlette.status import HTTP_200_OK

load_dotenv()

router = APIRouter(
    prefix="/tickers",
    tags=["tickers"],
    responses={404: {"description": "Not found"}},
)

# run daily


@router.get("/history", response_model=TickerResponseDTO, status_code=HTTP_200_OK)
async def archieve_ticker_price_history(params: TickerRequestDTO = Depends()):
    ticker = params.ticker
    data = await service.get_ticker_price_history(ticker)
    return data

# run daily


@router.get("/info", response_model=TickerResponseDTO, status_code=HTTP_200_OK)
async def achieve_ticker_info(params: TickerRequestDTO = Depends()):
    ticker = params.ticker
    data = await service.get_ticker_data(ticker)
    return data
