from fastapi import APIRouter, Depends
from dotenv import load_dotenv
from app.news.dto import AlphaVantageNewsQueryDTO, AlphaVantageNewsResponseDTO
from app.news import service
from starlette.status import HTTP_200_OK
from typing import Dict, List, Any

load_dotenv()

router = APIRouter(
    prefix="/news",
    tags=["news"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=AlphaVantageNewsResponseDTO, status_code=HTTP_200_OK)
async def archive_ticker_news(params: AlphaVantageNewsQueryDTO = Depends()):
    return await service(params)


@router.get("/6h", status_code=HTTP_200_OK)
async def archive_ticker_news():
    return await service.fetch_alpha_vantage_news_6h()


@router.get("/periodic-sentiment", response_model=Dict[str, Any], status_code=HTTP_200_OK)
async def get_news(ticker: str):
    return await service.get_news_sentiment_per_period_by_ticker(ticker)
