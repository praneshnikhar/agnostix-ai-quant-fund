"""Application settings.

All configuration is loaded from environment variables (prefix `API_`) with
`.env` support for local development. No secrets are ever hard-coded.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings (M0 foundation)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "ai-quant-fund-api"
    app_version: str = "0.1.0"
    environment: str = "dev"
    debug: bool = True
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Database / cache ---
    database_url: str = (
        "postgresql+asyncpg://fund:change-me-local-only@localhost:5432/fund"
    )
    redis_url: str = "redis://localhost:6379/0"

    # --- Model gateway providers (all optional) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None

    # --- Alpaca (PAPER TRADING ONLY; server-side only) ---
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_paper: bool = True
    alpaca_mcp_url: str | None = None

    # --- Auth foundation ---
    auth_secret: str = "generate-a-long-random-string"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
