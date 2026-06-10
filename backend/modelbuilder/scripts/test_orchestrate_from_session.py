from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODELBUILDER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAYLOAD = MODELBUILDER_ROOT / "examples" / "telecom_churn_and_research_rag_conversation_output.json"

sys.path.insert(0, str(MODELBUILDER_ROOT / "src"))

from vectorforge_v1.orchestrator.redis_store import conv_key  # noqa: E402
from vectorforge_v1.orchestrator.runner import _load_env_files  # noqa: E402


TERMINAL_STATUSES = {"completed", "failed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed Redis with a conversation output JSON and trigger "
            "POST /orchestrate/from-session/{session_id}."
        )
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_PAYLOAD,
        help=f"Conversation output JSON to write to Redis. Default: {DEFAULT_PAYLOAD}",
    )
    parser.add_argument(
        "--session-id",
        default=f"test_session_{uuid.uuid4().hex[:8]}",
        help="Session id used for vforge:conv:{session_id} and the trigger endpoint.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODEL_BUILDER_URL", "http://127.0.0.1:8005"),
        help="Modelbuilder base URL. Default: MODEL_BUILDER_URL or http://127.0.0.1:8005",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=3600,
        help="Redis TTL in seconds for the seeded conversation output.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Maximum seconds to poll the orchestrator run.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between orchestrator status polls.",
    )
    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="Only seed Redis and POST the trigger endpoint; do not poll status.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the seeded Redis key before exiting.",
    )
    return parser.parse_args()


def load_payload(path: Path, session_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected top-level JSON object in {path}")
    payload["session_id"] = session_id
    return payload


def redis_url_from_env() -> str:
    _load_env_files()
    redis_url = (
        os.environ.get("VECTORFORGE_REDIS_URL")
        or os.environ.get("VECTORFORGE_ELASTICACHE_REDIS_URL")
        or os.environ.get("ELASTICACHE_REDIS_URL")
        or os.environ.get("REDIS_URL")
    )
    if not redis_url:
        raise RuntimeError(
            "Redis is not configured. Set REDIS_URL or VECTORFORGE_REDIS_URL."
        )
    return redis_url


def http_json(method: str, url: str) -> dict[str, Any]:
    request = Request(url, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    return json.loads(body) if body else {}


def post_trigger(base_url: str, session_id: str) -> dict[str, Any]:
    target = f"{base_url.rstrip('/')}/orchestrate/from-session/{session_id}"
    return http_json("POST", target)


def poll_status(base_url: str, orch_id: str, timeout: int, interval: float) -> dict[str, Any]:
    status_url = f"{base_url.rstrip('/')}/orchestrate/{orch_id}"
    deadline = time.monotonic() + timeout
    last_status: dict[str, Any] = {}

    while time.monotonic() < deadline:
        last_status = http_json("GET", status_url)
        if last_status.get("status") in TERMINAL_STATUSES:
            return last_status
        time.sleep(interval)

    raise TimeoutError(
        f"Timed out after {timeout}s waiting for {orch_id}. "
        f"Last status: {last_status.get('status')}"
    )


def redis_client(redis_url: str):
    import redis.asyncio as aioredis

    if redis_url.startswith("rediss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return aioredis.from_url(
            redis_url,
            decode_responses=True,
            ssl=ctx,
            ssl_cert_reqs=None,
        )
    return aioredis.from_url(redis_url, decode_responses=True)


async def seed_redis(redis_url: str, session_id: str, payload: dict[str, Any], ttl: int) -> None:
    client = redis_client(redis_url)
    try:
        await client.set(conv_key(session_id), json.dumps(payload), ex=ttl)
    finally:
        await client.aclose()


async def delete_seed(redis_url: str, session_id: str) -> int:
    client = redis_client(redis_url)
    try:
        return int(await client.delete(conv_key(session_id)))
    finally:
        await client.aclose()


async def main() -> int:
    args = parse_args()
    payload = load_payload(args.json, args.session_id)
    redis_url = redis_url_from_env()
    redis_key = conv_key(args.session_id)

    await seed_redis(redis_url, args.session_id, payload, args.ttl)
    trigger = post_trigger(args.base_url, args.session_id)

    final_status: dict[str, Any] | None = None
    if not args.no_poll:
        final_status = poll_status(
            args.base_url,
            trigger["orch_id"],
            timeout=args.timeout,
            interval=args.interval,
        )

    deleted = await delete_seed(redis_url, args.session_id) if args.cleanup else 0

    print(
        json.dumps(
            {
                "session_id": args.session_id,
                "redis_key": redis_key,
                "payload_path": str(args.json),
                "trigger": trigger,
                "final_status": {
                    "status": final_status.get("status"),
                    "run_id": (final_status.get("result") or {}).get("run_id"),
                    "run_dir": (final_status.get("result") or {}).get("run_dir"),
                    "problem_count": len((final_status.get("result") or {}).get("problem_results") or []),
                    "error": final_status.get("error"),
                }
                if final_status
                else None,
                "cleanup_deleted": deleted,
            },
            indent=2,
        )
    )

    if final_status and final_status.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
