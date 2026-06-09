"""
ElastiCache (Redis)-backed session output store for orchestrator triggers.

A conversation client writes the orchestrator request body (matching
conv-output-schema.json) to ElastiCache for Redis:

    SET   vforge:conv:{session_id}            full JSON output (7-day TTL)
    XADD  vforge:stream:conv_complete         lightweight completion event

session_id is "{user_id}_{workspace_id}_{project_id}"
(e.g. f1050d64_622614c6_d172aafc).

This module only *reads* the output key so a trigger endpoint can pull the
request body on demand and hand it to the orchestrator.
"""
from __future__ import annotations

import json
import os
from typing import Any


CONV_KEY_PREFIX = "vforge:conv:"


def _elastic_cache_redis_url() -> str:
    # ElastiCache endpoints are typically TLS (rediss://) when in-transit
    # encryption is enabled; set the URL scheme accordingly in the env var.
    return (
        os.environ.get("VECTORFORGE_ELASTICACHE_REDIS_URL")
        or os.environ.get("ELASTICACHE_REDIS_URL")
        or os.environ.get("REDIS_URL")
        or "redis://localhost:6379"
    )


def conv_key(session_id: str) -> str:
    return f"{CONV_KEY_PREFIX}{session_id}"


async def get_session_output(session_id: str) -> dict[str, Any] | None:
    """
    Read and parse vforge:conv:{session_id} from ElastiCache for Redis.

    Returns the decoded JSON dict, or None if the key is absent.
    Raises ValueError if the stored value is not valid JSON.
    """
    import redis.asyncio as aioredis

    elastic_cache_redis_client = aioredis.from_url(_elastic_cache_redis_url(), decode_responses=True)
    try:
        raw = await elastic_cache_redis_client.get(conv_key(session_id))
    finally:
        await elastic_cache_redis_client.aclose()

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stored value for {conv_key(session_id)} is not valid JSON: {exc}") from exc
