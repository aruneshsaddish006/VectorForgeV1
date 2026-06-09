from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from vectorforge_v1.orchestrator.runner import _load_env_files
from vectorforge_v1.utils.elasticache_pubsub import publish_experiment_result


def main() -> int:
    _load_env_files()

    if not os.environ.get("VECTORFORGE_REDIS_URL"):
        raise RuntimeError("VECTORFORGE_REDIS_URL is not configured.")

    session_id = sys.argv[1] if len(sys.argv) > 1 else f"sess_test_{int(time.time())}"

    stream_id = publish_experiment_result(
        session_id=session_id,
        designer="manual-test",
        run_id="run_manual_test",
        round_number=1,
        experiment_id="exp_manual_1",
        config_path="/tmp/config.json",
        metrics_path="/tmp/metrics.json",
        config={
            "model": "manual-smoke-test",
            "architecture": "test-architecture",
        },
        metrics={
            "primary_metric": "accuracy",
            "primary_metric_value": 0.99,
        },
    )

    print(json.dumps({
        "session_id": session_id,
        "stream_id": stream_id,
        "stream": "vectorforge:experiments:results",
    }, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# 
# 
# from __future__ import annotations
# 
# import os
# import socket
# from urllib.parse import urlparse
# 
# import redis
# 
# from vectorforge_v1.orchestrator.runner import _load_env_files
# 
# 
# def main() -> int:
    # _load_env_files()
# 
    # url = os.environ.get("VECTORFORGE_REDIS_URL")
    # if not url:
        # raise RuntimeError("VECTORFORGE_REDIS_URL is not set")
# 
    # parsed = urlparse(url)
    # host = parsed.hostname
    # port = parsed.port or 6379
# 
    # print(f"URL scheme: {parsed.scheme}")
    # print(f"Host: {host}")
    # print(f"Port: {port}")
# 
    # print("\nTCP connect test...")
    # with socket.create_connection((host, port), timeout=10):
        # print("TCP: OK")
# 
    # print("\nRedis PING test...")
    # client = redis.Redis.from_url(url, socket_connect_timeout=10, socket_timeout=10, decode_responses=True)
    # print("PING:", client.ping())
# 
    # return 0
# 
# 
# if __name__ == "__main__":
    # raise SystemExit(main())
