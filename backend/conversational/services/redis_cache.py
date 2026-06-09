"""Async Redis cache for VectorForge session outputs.

Stores the final_output JSON under key: vforge:conv:{session_id}
TTL: 7 days (orchestrators read within this window).

The key schema is intentionally simple — orchestrators read by session_id only.
Uses ssl=True automatically when the URL scheme is rediss://.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any

import redis.asyncio as aioredis

from conversational.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "vforge:conv:"
_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def _session_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def _make_client(url: str) -> aioredis.Redis:
    """Build an async Redis client, enabling SSL for rediss:// URLs."""
    if url.startswith("rediss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return aioredis.from_url(url, decode_responses=True, ssl_cert_reqs=None, ssl=ctx)
    return aioredis.from_url(url, decode_responses=True)


async def write_session_output(session_id: str, output: dict[str, Any]) -> None:
    """Write the final output JSON to Redis keyed by session_id.

    Called by the API route when the conversation reaches status=complete.
    The JSON structure exactly matches conv-output-schema.json so orchestrators
    can deserialise it without transformation.

    Errors are logged but never raised — a Redis failure must not block the
    API response to the user.
    """
    settings = get_settings()
    try:
        client = _make_client(settings.redis_url)
        async with client:
            await client.set(
                _session_key(session_id),
                json.dumps(output),
                ex=_TTL_SECONDS,
            )
        logger.info("Redis: wrote session output for session=%s", session_id)
    except Exception as exc:
        logger.error("Redis write failed for session=%s: %s", session_id, exc)


async def read_session_output(session_id: str) -> dict[str, Any] | None:
    """Read session output from Redis. Returns None if key is absent or Redis is down."""
    settings = get_settings()
    try:
        client = _make_client(settings.redis_url)
        async with client:
            raw = await client.get(_session_key(session_id))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.error("Redis read failed for session=%s: %s", session_id, exc)
        return None
