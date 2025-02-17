from pydantic import BaseModel, Field
from typing import Optional
from typing import List

class AlphaVantageNewsQueryDTO(BaseModel):
    from_date: str = Field(...)
    to_date: str = Field(...)
    tickers: Optional[str] = Field(None)
    limit: Optional[int] = Field(1000)
    sort: Optional[str] = Field("RELEVANCE")


class TopicSentiment(BaseModel):
    topic: str = Field(...)
    relevance_score: float = Field(...)

class TickerSentiment(BaseModel):
    ticker: str = Field(...)
    relevance_score: float = Field(...)
    ticker_sentiment_score: float = Field(...)
    ticker_sentiment_label: str = Field(...)

class AlphaVantageNewsDTO(BaseModel):
    # _id: str = Field(...)
    title: str = Field(...)
    url: str = Field(...)
    time_published: str = Field(...)
    authors: List[str] = Field(...)
    summary: str = Field(...)
    banner_image: str = Field(...)
    source: str = Field(...)
    category_within_source: str = Field(...)
    source_domain: str = Field(...)
    topics: List[TopicSentiment] = Field(...)
    overall_sentiment_score: float = Field(...)
    overall_sentiment_label: str = Field(...)
    ticker_sentiment: List[TickerSentiment] = Field(...)

class AlphaVantageNewsResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
