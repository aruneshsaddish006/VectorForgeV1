from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ExperimentResultsStreamReader:
    def poll(
        self,
        *,
        session_id: str,
        after: str = "0-0",
        count: int = 100,
        block_ms: int = 0,
    ) -> dict[str, Any]:
        redis_url = _load_redis_url()
        if not redis_url:
            return {
                "session_id": session_id,
                "cursor": after,
                "stream": _redis_key("experiments:results"),
                "events": [],
                "error": "VECTORFORGE_REDIS_URL is not configured.",
            }

        import redis

        stream = _redis_key("experiments:results")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        xread_kwargs: dict[str, Any] = {"count": count}
        if block_ms > 0:
            xread_kwargs["block"] = block_ms
        rows = client.xread({stream: after}, **xread_kwargs)

        cursor = after
        events: list[dict[str, Any]] = []
        for _, messages in rows:
            for message_id, fields in messages:
                cursor = message_id
                if fields.get("session_id") != session_id:
                    continue
                payload = _decode_payload(fields)
                events.append(
                    {
                        "id": message_id,
                        "payload": payload,
                    }
                )

        return {
            "session_id": session_id,
            "cursor": cursor,
            "stream": stream,
            "events": events,
            "error": None,
        }


def _decode_payload(fields: dict[str, Any]) -> dict[str, Any]:
    payload = fields.get("payload")
    if not payload:
        return fields
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


def _redis_key(name: str) -> str:
    prefix = os.environ.get("VECTORFORGE_REDIS_CHANNEL_PREFIX", "vectorforge").strip(":")
    return f"{prefix}:{name.lstrip(':')}" if prefix else name.lstrip(":")


def _load_redis_url() -> str | None:
    _load_env_files()
    return os.environ.get("VECTORFORGE_REDIS_URL")


def _load_env_files() -> None:
    for path in _candidate_env_paths():
        if path.exists():
            _load_env_file(path)


def _candidate_env_paths() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[2]
    repo_root = backend_root.parent
    package_root = repo_root / "src" / "vectorforge_v1"
    return [
        Path.cwd() / ".env",
        backend_root / ".env",
        repo_root / ".env",
        repo_root.parent / ".env",
        package_root / ".env",
    ]


def _load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


experiment_results_stream = ExperimentResultsStreamReader()
