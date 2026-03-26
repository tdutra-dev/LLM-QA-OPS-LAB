"""
Step 6 — Redis response cache.

Design decisions:
  • Uses redis-py synchronous client (no asyncio overhead for simple JSON blobs).
  • Graceful degradation: if Redis is unavailable the endpoints still work,
    they just compute fresh every time. No exception propagates to the caller.
  • Cache keys are plain strings: "cache:metrics" / "cache:analytics".
  • TTL is 30 s by default — short enough to stay fresh, long enough to absorb
    traffic spikes.
  • Invalidation is write-through: POST /evaluate always deletes both keys so
    subsequent reads are always consistent.

Key concepts demonstrated:
  • redis.from_url()     — parses REDIS_URL env var (docker-compose injects it)
  • r.get() / r.set()   — binary-safe GET/SET with optional EX (seconds TTL)
  • r.delete()          — remove one or more keys atomically
  • r.ping()            — liveness probe used in the /health check
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 30  # seconds

# Cache key constants — single source of truth so invalidation is reliable
KEY_METRICS = "cache:metrics"
KEY_ANALYTICS = "cache:analytics"
ALL_KEYS = (KEY_METRICS, KEY_ANALYTICS)


def _get_client() -> redis.Redis:
    """
    Create a Redis client from the REDIS_URL env var.

    decode_responses=False keeps values as bytes so json.loads() works directly.
    socket_connect_timeout=2 prevents long hangs when Redis is down.
    """
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


# Module-level singleton — one connection pool shared across requests.
# Initialized lazily on first use so env vars are read AFTER uvicorn/lifespan
# sets them (important with --reload mode which forks a subprocess).
_redis: redis.Redis | None = None
_initialized = False


def _init() -> None:
    """Connect once and cache the result in the module-level singleton."""
    global _redis, _initialized
    if _initialized:
        return
    _initialized = True
    try:
        client = _get_client()
        client.ping()
        _redis = client
        logger.info("[cache] Redis connected: %s", os.environ.get("REDIS_URL", "redis://localhost:6379"))
    except Exception as exc:
        logger.warning("[cache] Redis unavailable (%s) — caching disabled", exc)
        _redis = None


# ── Public API ─────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if the Redis client is alive (used by /health)."""
    _init()
    if _redis is None:
        return False
    try:
        return bool(_redis.ping())
    except Exception:
        return False


def get(key: str) -> Any | None:
    """
    Return the cached value for *key*, or None on miss / Redis error.

    The value was stored as JSON bytes; we decode and parse here.
    """
    _init()
    if _redis is None:
        return None
    try:
        raw = _redis.get(key)
        if raw is None:
            return None
        result = json.loads(raw)
        logger.debug("[cache] HIT  %s", key)
        return result
    except Exception as exc:
        logger.warning("[cache] GET error for %s: %s", key, exc)
        return None


def set(key: str, value: Any, ttl: int = _DEFAULT_TTL) -> None:
    """
    Serialise *value* to JSON and store it under *key* with a TTL.

    EX=ttl means the key is automatically deleted after *ttl* seconds
    — no stale data can accumulate even if invalidation is missed.
    """
    _init()
    if _redis is None:
        return
    try:
        _redis.set(key, json.dumps(value), ex=ttl)
        logger.debug("[cache] SET  %s (TTL=%ds)", key, ttl)
    except Exception as exc:
        logger.warning("[cache] SET error for %s: %s", key, exc)


def invalidate(*keys: str) -> None:
    """
    Delete one or more cache keys atomically (write-through invalidation).

    Called by POST /evaluate so the next GET /metrics and GET /analytics
    always reflect the just-saved record.
    """
    _init()
    if _redis is None:
        return
    try:
        _redis.delete(*keys)
        logger.debug("[cache] DEL  %s", keys)
    except Exception as exc:
        logger.warning("[cache] DEL error for %s: %s", keys, exc)
