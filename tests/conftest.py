"""
pytest configuration and shared fixtures for the test suite.

Unit tests use:
  - SQLite in-memory (via aiosqlite) for Postgres repository tests
    → No live Postgres connection required
  - mongomock-motor for MongoDB tests
    → No live MongoDB connection required

Integration tests (marked @pytest.mark.integration) are skipped unless
the DATABASE_URL env var points at a real Postgres instance.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


# ---------------------------------------------------------------------------
# SQLite in-memory engine for unit tests
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """
    Yield a throwaway SQLite AsyncSession with all tables created.
    Each test gets a fresh in-memory DB.
    """
    engine = create_async_engine(SQLITE_URL, echo=False)

    # Create all mapped tables in the in-memory SQLite DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        yield session

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# MongoDB mock engine for unit tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_mongo_db():
    """Return a mongomock-motor database instance."""
    import mongomock_motor

    client = mongomock_motor.AsyncMongoMockClient()
    db = client["test_db"]
    yield db
    client.close()


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests as requiring a live database (deselect with -m 'not integration')",
    )
