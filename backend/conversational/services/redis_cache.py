"""Async Redis cache for VectorForge session outputs.

Two write paths on conversation completion:

1. SET  vforge:conv:{session_id}  → full JSON output (7-day TTL)
   Orchestrators read this key directly by session_id.

2. XADD vforge:stream:conv_complete → lightweight completion event
   Downstream services subscribe via XREAD/consumer-groups.
   Event fields: session_id, event, output_key, timestamp

Stream contract for the integrating developer
----------------------------------------------
Stream key : vforge:stream:conv_complete
Message fields:
  session_id  string  — the user_workspace_project identifier
  event       string  — always "conversation_complete"
  output_key  string  — Redis key holding the full JSON ("vforge:conv:{session_id}")
  timestamp   string  — ISO-8601 UTC timestamp

Consumer example (Python):
  entries = await redis.xread({"vforge:stream:conv_complete": "$"}, block=0)
  for stream, messages in entries:
      for msg_id, fields in messages:
          output = await redis.get(fields["output_key"])
          payload = json.loads(output)

Uses ssl=True automatically when the URL scheme is rediss://.
"""

from __future__ import annotations

import json
import logging
import ssl
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from conversational.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "vforge:conv:"
_STREAM_KEY = "vforge:stream:conv_complete"
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
    """Write the final output JSON to Redis and publish a stream completion event.

    Two operations in one call:
      1. SET  vforge:conv:{session_id}        — full JSON, 7-day TTL
      2. XADD vforge:stream:conv_complete     — lightweight event for subscribers

    Errors are logged but never raised — Redis failures must not block the
    API response to the user.
    """
    settings = get_settings()
    key = _session_key(session_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        client = _make_client(settings.redis_url)
        async with client:
            await client.set(key, json.dumps(output), ex=_TTL_SECONDS)
            await client.xadd(
                _STREAM_KEY,
                {
                    "session_id": session_id,
                    "event": "conversation_complete",
                    "output_key": key,
                    "timestamp": now,
                },
            )
        logger.info("Redis: wrote output + stream event for session=%s", session_id)
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
