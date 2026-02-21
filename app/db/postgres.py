"""
Async SQLAlchemy engine and session factory.

DATABASE_URL is read from the environment. Accepted schemes (all normalised
to postgresql+psycopg:// for psycopg3 async driver):
    postgresql+psycopg://...    ← explicit, ideal
    postgresql+asyncpg://...    ← auto-fixed (asyncpg has SCRAM bug with Supabase)
    postgresql://...            ← auto-fixed
    postgres://...              ← auto-fixed (common Supabase / Heroku form)
    sqlite+aiosqlite://         ← used by unit tests

The engine is created lazily on first use so this module can be imported
during testing even when DATABASE_URL is not yet set.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()


def _normalise_url(url: str) -> str:
    """
    Ensure the URL uses the psycopg3 async driver.
    Rewrites any plain postgres:// or postgresql:// (which default to psycopg2)
    and any postgresql+asyncpg:// (known broken with Supabase pgBouncer SCRAM).
    """
    for prefix in ("postgresql+asyncpg://", "postgresql+asyncio://", "asyncpg://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _get_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file.\n"
            "Format: postgresql+asyncpg://<user>:<pass>@<host>:<port>/<db>\n"
            "Get it from: Supabase → Settings → Database → Connection String → URI"
        )
    return _normalise_url(raw)


# ---------------------------------------------------------------------------
# Lazy singletons — created on first access
# ---------------------------------------------------------------------------

_engine = None
_factory: async_sessionmaker | None = None


def _get_factory() -> async_sessionmaker:
    global _engine, _factory
    if _factory is None:
        url = _get_database_url()
        connect_args: dict = {}
        if url.startswith("postgresql+psycopg://"):
            # psycopg3 defaults to SCRAM-SHA-256-PLUS (TLS channel binding) when
            # SSL is active. Supabase's pgBouncer does NOT support the -PLUS
            # variant and rejects it as "Wrong password" even with correct creds.
            # Disabling channel binding forces plain SCRAM-SHA-256, which works.
            connect_args["channel_binding"] = "disable"
            # prepare_threshold=0 disables server-side prepared statements,
            # required for pgBouncer Transaction Pooler (port 6543) compatibility.
            connect_args["prepare_threshold"] = 0
            # Supabase requires SSL on all pooler connections.
            if "supabase" in url or "pooler" in url:
                connect_args["sslmode"] = "require"
        _engine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args=connect_args,
        )
        _factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _factory


def AsyncSessionLocal() -> AsyncSession:  # noqa: N802
    """
    Return an async context-manager session.

    Usage (in repositories / services):
        async with AsyncSessionLocal() as session:
            ...
    """
    return _get_factory()()


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one session per request."""
    async with _get_factory()() as session:
        yield session
