"""Integration tests: API → PostgreSQL and API → Redis.

Skipped automatically when infrastructure is unavailable, so normal CI
never depends on live services. Run explicitly with:
    pytest tests/integration -m integration
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _db_configured() -> bool:
    return bool(os.environ.get("INTEGRATION_DB_URL"))


def _redis_configured() -> bool:
    return bool(os.environ.get("INTEGRATION_REDIS_URL"))


@pytest.mark.skipif(not _db_configured(), reason="INTEGRATION_DB_URL not set")
async def test_postgres_connectivity() -> None:
    from sqlalchemy import text

    from app.db.session import create_engine

    engine = create_engine(os.environ["INTEGRATION_DB_URL"])
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


@pytest.mark.skipif(not _redis_configured(), reason="INTEGRATION_REDIS_URL not set")
async def test_redis_connectivity() -> None:
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        os.environ["INTEGRATION_REDIS_URL"], decode_responses=True
    )
    try:
        assert await client.ping() is True
        await client.set("fund:m0:test", "ok", ex=60)
        assert await client.get("fund:m0:test") == "ok"
    finally:
        close = getattr(client, "aclose", None) or client.close
        await close()
