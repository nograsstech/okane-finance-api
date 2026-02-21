"""
MongoDB client — module-level singleton using motor (async).

Instead of creating a new client on every request (the old behaviour),
this module creates a single AsyncIOMotorClient at import time and caches
the resolved Database object.  Callers continue to use connect_mongodb()
for backward compatibility; it now simply returns the cached Database.
"""

from __future__ import annotations

import os
import certifi
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

load_dotenv()

COLLECTIONS = {
    "stock_lists": "stock_lists",
    "news": "news",
    "news_with_sentiment": "news_with_sentiment",
    "price_histories": "price_histories",
    "ticker_infos": "ticker_infos",
}

# ---------------------------------------------------------------------------
# Singleton client — created once at module import time.
# ---------------------------------------------------------------------------
_MONGO_URI = (
    f"mongodb+srv://{os.environ.get('MONGO_USER')}:{os.environ.get('MONGO_PASSWORD')}"
    f"@develop.dkur4lg.mongodb.net/?retryWrites=true&w=majority"
)

_client: AsyncIOMotorClient = AsyncIOMotorClient(
    _MONGO_URI,
    server_api=ServerApi("1"),
    tlsCAFile=certifi.where(),
)

_db_name: str = "production" if os.environ.get("ENV") == "production" else "develop"
_database = _client[_db_name]


async def connect_mongodb():
    """
    Return the cached Motor database instance.

    Kept as an async function for full backward compatibility with all callers
    that do ``db = await connect_mongodb()``.
    """
    return _database