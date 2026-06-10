"""Test Redis connection and read experiment plan output.

Usage:
    # Read specific session (positional arg)
    python scripts/read_redis_output.py <session_id>

    # Read last N stream events (default 5)
    python scripts/read_redis_output.py --stream
    python scripts/read_redis_output.py --stream --count 10

    # Connection test only
    python scripts/read_redis_output.py --ping

Run from the conversational/ directory so .env is auto-loaded:
    cd backend/conversational && python scripts/read_redis_output.py <session_id>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env from conversational/ directory before importing redis
# ---------------------------------------------------------------------------
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import redis.asyncio as aioredis  # noqa: E402

_KEY_PREFIX = "vforge:conv:"
_STREAM_KEY = "vforge:stream:conv_complete"


def _make_client(url: str) -> aioredis.Redis:
    if url.startswith("rediss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return aioredis.from_url(url, decode_responses=True, ssl_cert_reqs=None, ssl=ctx)
    return aioredis.from_url(url, decode_responses=True)


async def test_connection(url: str) -> bool:
    print(f"[ping] connecting to {url[:50]}...")
    try:
        async with _make_client(url) as client:
            resp = await client.ping()
        ok = resp is True
        print(f"[ping] {'OK — Redis is reachable' if ok else 'FAILED — unexpected response'}")
        return ok
    except Exception as exc:
        print(f"[ping] FAILED — {exc}")
        return False


async def read_session(url: str, session_id: str) -> None:
    key = f"{_KEY_PREFIX}{session_id}"
    print(f"\n[read] key = {key}")
    try:
        async with _make_client(url) as client:
            raw = await client.get(key)
            ttl = await client.ttl(key)
        if raw is None:
            print("[read] NOT FOUND — key is absent or expired")
            return
        payload = json.loads(raw)
        remaining_h = ttl // 3600 if ttl > 0 else "unknown"
        print(f"[read] found — TTL {ttl}s ({remaining_h}h remaining)\n")
        print(json.dumps(payload, indent=2, default=str))
    except Exception as exc:
        print(f"[read] ERROR — {exc}")


async def read_stream(url: str, count: int) -> None:
    print(f"\n[stream] key = {_STREAM_KEY}  (last {count} events)")
    try:
        async with _make_client(url) as client:
            entries = await client.xrevrange(_STREAM_KEY, count=count)
        if not entries:
            print("[stream] no events found")
            return
        for msg_id, fields in entries:
            print(f"\n  id        : {msg_id}")
            for k, v in fields.items():
                print(f"  {k:<12}: {v}")
    except Exception as exc:
        print(f"[stream] ERROR — {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VectorForge Redis output reader")
    parser.add_argument("session_id", nargs="?", help="Session ID to read from Redis")
    parser.add_argument("--ping", action="store_true", help="Test connection only")
    parser.add_argument("--stream", action="store_true", help="Print recent stream events")
    parser.add_argument("--count", type=int, default=5, help="Number of stream events (default 5)")
    args = parser.parse_args()

    url = os.environ.get("REDIS_URL", "")
    if not url:
        print("ERROR: REDIS_URL not set. Run from backend/conversational/ or export REDIS_URL.")
        sys.exit(1)

    async def run() -> None:
        ok = await test_connection(url)
        if not ok:
            sys.exit(1)

        if args.session_id:
            await read_session(url, args.session_id)

        if args.stream:
            await read_stream(url, args.count)

        if not args.session_id and not args.stream and not args.ping:
            parser.print_help()

    asyncio.run(run())


if __name__ == "__main__":
    main()
