from pydantic import BaseModel, Field
from typing import Optional


class TickerRequestDTO(BaseModel):
    ticker: str = Field(...)


class TickerResponseDTO(BaseModel):
    status: int = Field(...)
    message: str = Field(...)
