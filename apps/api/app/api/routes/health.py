"""Health endpoint — reports API, database, and Redis status."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database_connection
from app.schemas.contracts import HealthResponse
from app.services.redis_client import check_redis_connection

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness/readiness probe covering api + postgres + redis."""
    settings = get_settings()
    db_ok = await check_database_connection()
    redis_ok = await check_redis_connection()

    if db_ok and redis_ok:
        status: str = "healthy"
    elif db_ok or redis_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,  # type: ignore[arg-type]
        version=settings.app_version,
        environment=settings.environment,
        database=db_ok,
        redis=redis_ok,
    )
