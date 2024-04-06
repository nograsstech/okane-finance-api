from pydantic import BaseModel, Field
from typing import Optional

class AlphaVantageNewsQueryDTO(BaseModel):
    from_date: str = Field(...)
    to_date: str = Field(...)
    tickers: Optional[str] = Field(None)
    limit: Optional[int] = Field(1000)
    sort: Optional[str] = Field("RELEVANCE")

class AlphaVantageNewsResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
