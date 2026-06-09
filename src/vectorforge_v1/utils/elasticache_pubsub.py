from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ElastiCacheStreamWriter:
    def __init__(self, redis_url: str | None = None, key_prefix: str | None = None) -> None:
        self.redis_url = redis_url or os.environ.get("VECTORFORGE_REDIS_URL")
        self.key_prefix = key_prefix or os.environ.get("VECTORFORGE_REDIS_CHANNEL_PREFIX", "vectorforge")
        self.stream_maxlen = _optional_positive_int(os.environ.get("VECTORFORGE_REDIS_STREAM_MAXLEN"))
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.redis_url)

    def append_json(self, stream: str, payload: dict[str, Any], fields: dict[str, Any] | None = None) -> str | None:
        if not self.enabled:
            return None
        try:
            stream_fields = {
                key: str(value)
                for key, value in (fields or {}).items()
                if value is not None
            }
            stream_fields["payload"] = json.dumps(payload, default=str)
            kwargs = {"maxlen": self.stream_maxlen, "approximate": True} if self.stream_maxlen else {}
            stream_id = self._get_client().xadd(self._key(stream), stream_fields, **kwargs)
            logger.debug("ElastiCacheStreamWriter: appended to %s -> %s", stream, stream_id)
            return str(stream_id)
        except Exception as exc:
            logger.warning("ElastiCacheStreamWriter: append failed for stream %s: %s", stream, exc)
            return None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.redis_url:
                raise RuntimeError("VECTORFORGE_REDIS_URL is required for Redis Streams.")
            import redis

            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _key(self, key: str) -> str:
        prefix = self.key_prefix.strip(":")
        return f"{prefix}:{key.lstrip(':')}" if prefix else key.lstrip(":")


def publish_experiment_result(
    *,
    session_id: str,
    designer: str,
    run_id: str,
    round_number: int,
    experiment_id: str,
    config_path: str | Path,
    metrics_path: str | Path,
    config: dict[str, Any],
    metrics: dict[str, Any],
) -> str | None:
    payload = {
        "session_id": session_id,
        "designer": designer,
        "run_id": run_id,
        "round": round_number,
        "experiment_id": experiment_id,
        "config_path": str(config_path),
        "metrics_path": str(metrics_path),
        "config": config,
        "metrics": metrics,
    }
    return ElastiCacheStreamWriter().append_json(
        "experiments:results",
        payload,
        fields={
            "session_id": session_id,
            "run_id": run_id,
            "designer": designer,
            "round": round_number,
            "experiment_id": experiment_id,
        },
    )


def publish_end_of_message(*, session_id: str, run_id: str) -> str | None:
    payload = {
        "session_id": session_id,
        "run_id": run_id,
        "event_type": "end",
        "body": "END OF MESSAGE",
    }
    return ElastiCacheStreamWriter().append_json(
        "experiments:results",
        payload,
        fields={
            "session_id": session_id,
            "run_id": run_id,
            "event_type": "end",
        },
    )


def _optional_positive_int(value: str | None) -> int | None:
    if not value:
        return None
    resolved = int(value)
    return resolved if resolved > 0 else None
