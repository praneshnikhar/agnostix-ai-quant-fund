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
    database_url: str = "postgresql+asyncpg://fund:change-me-local-only@localhost:5432/fund"
    redis_url: str = "redis://localhost:6379/0"

    # --- Model gateway providers (all optional) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    # Ollama (local models): fully configurable host + explicit model id;
    # nothing is hardcoded to localhost or any specific model/GPU.
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    ollama_timeout_seconds: float = 300.0
    # OpenRouter (cloud aggregator): arbitrary model ids are supported —
    # never hardcode one model as the only option. Credentials are
    # server-side only and never logged/persisted/returned to the frontend.
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_timeout_seconds: float = 120.0
    openrouter_max_retries: int = 2
    openrouter_retry_backoff_seconds: float = 0.5
    # Custom / self-hosted models (vLLM, TGI, OpenAI-compatible servers,
    # future fine-tuned Agnostix endpoints). Fully configurable; credentials
    # optional; initialized lazily only when this provider is requested.
    custom_model_base_url: str | None = None
    custom_model_api_key: str | None = None
    custom_model_id: str | None = None
    custom_model_timeout_seconds: float = 120.0
    custom_model_headers: dict[str, str] = {}

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
