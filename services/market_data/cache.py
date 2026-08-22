"""Redis cache helper (M1).

Short-lived cache only — PostgreSQL remains the durable store. Cache
entries always carry received_at so consumers can judge freshness; the
cache never makes stale data look fresh. Degrades to a no-op when Redis
is unavailable so caching is never a correctness dependency.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60


def _key(datatype: str, symbol: str, timeframe: str | None = None) -> str:
    base = f"m1:{datatype}:{symbol.upper()}"
    return f"{base}:{timeframe}" if timeframe else base


class _NoopCache:
    async def get_json(self, key: str) -> Any:
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        return None


class RedisCache(_NoopCache):
    def __init__(self, url: str) -> None:
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError("redis package not installed") from exc
        self._redis = Redis.from_url(url, decode_responses=True)

    async def get_json(self, key: str) -> Any:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        entry = json.loads(raw)
        # Entry shape: {"received_at": iso, "payload": ...}
        if not isinstance(entry, dict) or "received_at" not in entry:
            return None  # malformed/foreign entry treated as miss
        return entry["payload"]

    async def set_json(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        entry = {
            "received_at": datetime.now(UTC).isoformat(),
            "payload": value,
        }
        await self._redis.set(key, json.dumps(entry), ex=ttl_seconds)


def get_cache() -> _NoopCache | RedisCache:
    """Factory: real cache when REDIS_URL set and reachable config exists,
    otherwise a silent no-op."""
    url = os.environ.get("REDIS_URL")
    if not url:
        return _NoopCache()
    try:
        return RedisCache(url)
    except Exception as exc:  # pragma: no cover - env-dependent
        logger.warning("redis cache unavailable (%s); continuing without cache", exc)
        return _NoopCache()


__all__ = ["DEFAULT_TTL_SECONDS", "RedisCache", "_NoopCache", "_key", "get_cache"]
