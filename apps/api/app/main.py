"""FastAPI application factory — AI Quant Fund API (M0)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    events,
    health,
    markets,
    options,
    playground,
    providers,
    research,
    trading,
    ws,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle."""
    settings = get_settings()
    configure_logging(level=settings.log_level)
    logger = get_logger("app")
    logger.info(
        "api_starting",
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    from app.services.redis_client import close_redis

    await close_redis()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(markets.router)
    app.include_router(research.router)
    app.include_router(events.router)
    app.include_router(providers.router)
    app.include_router(ws.router)
    app.include_router(options.router)
    app.include_router(trading.router)
    app.include_router(playground.router)

    return app


app = create_app()
