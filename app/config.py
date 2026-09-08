from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ORIGINS = (
    "https://okane-signals.vercel.app",
    "https://okane-signals-git-dev-pointmekins-projects.vercel.app",
    "https://okane-signals-i66hoyzcj-pointmekins-projects.vercel.app",
    "https://okane-signals-web.vercel.app",
    "https://okane-signals.dhanabordee.com",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://localhost:3000",
)
DEFAULT_CORS_ORIGIN_REGEX = (
    r"^https://(.*\.vercel\.app|.*\.dhanabordee\.com|okane-signals\.dhanabordee\.com)$"
)


class Settings(BaseSettings):
    """Environment-backed settings used by the core API paths."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    mongo_user: str | None = Field(default=None, validation_alias="MONGO_USER")
    mongo_password: str | None = Field(default=None, validation_alias="MONGO_PASSWORD")
    environment: str = Field(default="development", validation_alias="ENV")
    api_username: str | None = Field(default=None, validation_alias="OKANE_FINANCE_API_USER")
    api_password: str | None = Field(default=None, validation_alias="OKANE_FINANCE_API_PASSWORD")
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    cors_origin_regex: str = DEFAULT_CORS_ORIGIN_REGEX


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
