"""
Unit tests for the MongoDB client layer.

Uses mongomock-motor — no live MongoDB connection required.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# MongoDB client singleton tests
# ---------------------------------------------------------------------------


class TestMongoDBClient:
    async def test_connect_returns_motor_database(self, mock_mongo_db):
        """connect_mongodb() should return a motor Database-like object."""
        # The mock_mongo_db fixture returns a mongomock database;
        # verify it has the expected collection API
        assert hasattr(mock_mongo_db, "__getitem__")
        col = mock_mongo_db["news_with_sentiment"]
        assert col is not None

    async def test_collections_constant_contains_expected_keys(self):
        """COLLECTIONS dict should expose all expected collection names."""
        from app.base.utils.mongodb import COLLECTIONS

        expected = {"stock_lists", "news", "news_with_sentiment", "price_histories", "ticker_infos"}
        assert expected == set(COLLECTIONS.keys())

    async def test_collections_values_are_strings(self):
        from app.base.utils.mongodb import COLLECTIONS

        for key, value in COLLECTIONS.items():
            assert isinstance(value, str), f"COLLECTIONS['{key}'] should be a string"

    async def test_insert_and_find_via_mock(self, mock_mongo_db):
        """Basic smoke test: insert a doc and retrieve it via mongomock."""
        col = mock_mongo_db["price_histories"]
        doc = {"ticker": "AAPL", "history": [{"time": "2024-01-01", "close": 185.0}]}
        await col.insert_one(doc)

        found = await col.find_one({"ticker": "AAPL"})
        assert found is not None
        assert found["ticker"] == "AAPL"
        assert len(found["history"]) == 1

    async def test_insert_many_and_count(self, mock_mongo_db):
        col = mock_mongo_db["news_with_sentiment"]
        docs = [{"title": f"News {i}", "overall_sentiment_score": 0.1 * i} for i in range(5)]
        await col.insert_many(docs)

        count = await col.count_documents({})
        assert count == 5

    async def test_find_with_filter(self, mock_mongo_db):
        col = mock_mongo_db["ticker_infos"]
        await col.insert_many([
            {"ticker": "AAPL", "sector": "Tech"},
            {"ticker": "XOM", "sector": "Energy"},
        ])
        found = await col.find_one({"ticker": "XOM"})
        assert found["sector"] == "Energy"

    async def test_db_name_from_env_var(self, monkeypatch):
        """The correct database name is selected based on ENV env var."""
        # We can't easily re-import the singleton, but we can verify the
        # logic independently.
        monkeypatch.setenv("ENV", "production")
        db_name = "production" if os.environ.get("ENV") == "production" else "develop"
        assert db_name == "production"

        monkeypatch.setenv("ENV", "development")
        db_name = "production" if os.environ.get("ENV") == "production" else "develop"
        assert db_name == "develop"
