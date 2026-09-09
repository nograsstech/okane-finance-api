"""Lazy process-wide MongoDB client used by news and ticker services."""

from __future__ import annotations

from urllib.parse import quote_plus

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi

from app.config import get_settings

COLLECTIONS = {
    "stock_lists": "stock_lists",
    "news": "news",
    "news_with_sentiment": "news_with_sentiment",
    "price_histories": "price_histories",
    "ticker_infos": "ticker_infos",
}

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def _get_database() -> AsyncIOMotorDatabase:
    global _client, _database
    if _database is None:
        settings = get_settings()
        if settings.mongo_user is None or settings.mongo_password is None:
            raise RuntimeError("MONGO_USER and MONGO_PASSWORD are not configured")
        uri = (
            f"mongodb+srv://{quote_plus(settings.mongo_user)}:"
            f"{quote_plus(settings.mongo_password)}"
            "@develop.dkur4lg.mongodb.net/?retryWrites=true&w=majority"
        )
        _client = AsyncIOMotorClient(
            uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )
        database_name = "production" if settings.environment == "production" else "develop"
        _database = _client[database_name]
    return _database


async def connect_mongodb():
    """Return the cached database, creating the Motor client on first use."""
    return _get_database()
