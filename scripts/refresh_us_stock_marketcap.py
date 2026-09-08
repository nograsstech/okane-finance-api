"""Refresh the top US companies by market cap in MongoDB.

Run from the repository root with ``uv run python scripts/refresh_us_stock_marketcap.py``.
MongoDB credentials are read from the existing ``MONGO_USER`` and
``MONGO_PASSWORD`` environment variables.
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import aiohttp
import pandas as pd
from loguru import logger

from app.base.utils.mongodb import COLLECTIONS, connect_mongodb

DATA_DIRECTORY = Path("data/us-stock-list")
COMPANIES_CSV_URL = "https://companiesmarketcap.com/?download=csv"


async def fetch_companies_csv() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(COMPANIES_CSV_URL) as response:
            response.raise_for_status()
            return await response.text()


def save_companies_csv(contents: str, date: str) -> Path:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIRECTORY / f"{date}.csv"
    rows = csv.reader(StringIO(contents))
    with output_path.open("w", newline="") as output_file:
        csv.writer(output_file).writerows(rows)
    return output_path


async def refresh_stock_list() -> None:
    date = datetime.now().strftime("%d-%m-%Y")
    previous_date = (datetime.now() - timedelta(days=31)).strftime("%d-%m-%Y")

    csv_path = save_companies_csv(await fetch_companies_csv(), date)
    top_companies = pd.read_csv(csv_path).head(150)

    database = await connect_mongodb()
    collection = database[COLLECTIONS["stock_lists"]]
    await collection.delete_many({"date": previous_date})

    previous_csv_path = DATA_DIRECTORY / f"{previous_date}.csv"
    previous_csv_path.unlink(missing_ok=True)

    result = await collection.insert_one(
        {
            "date": date,
            "data": top_companies.to_dict("records"),
        }
    )
    logger.success("Inserted US stocks for {} with ID {}", date, result.inserted_id)


if __name__ == "__main__":
    asyncio.run(refresh_stock_list())
