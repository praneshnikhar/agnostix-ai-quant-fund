"""Redis client management (cache/queue/coordination — never source of truth)."""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Lazily create the process-wide async Redis client."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def check_redis_connection() -> bool:
    """Return True if PING succeeds."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis client on shutdown."""
    global _redis
    if _redis is not None:
        # redis-py >=5 exposes aclose(); fall back for older versions.
        close = getattr(_redis, "aclose", None) or _redis.close
        await close()
        _redis = None
