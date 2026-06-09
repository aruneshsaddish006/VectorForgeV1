# Redis Integration Contract — VectorForge Conversational Service

Share this document with any downstream developer who needs to consume
conversation outputs.

---

## Overview

When a user completes the conversational flow and confirms the final plan,
the conversational service writes to Redis in two ways simultaneously:

| Write | Key / Stream | Purpose |
|-------|-------------|---------|
| `SET` | `vforge:conv:{session_id}` | Full JSON output — pulled by orchestrators on demand |
| `XADD` | `vforge:stream:conv_complete` | Lightweight event — push notification the moment a session completes |

---

## 1. Output Key (SET)

### Key format

```
vforge:conv:{session_id}
```

`session_id` is `{user_id}_{workspace_id}_{project_id}` — e.g.
`f1050d64_622614c6_d172aafc`.

### TTL

7 days from write time. Reset on re-run of the same workspace + project.

### Value — full JSON output

Structure matches `conv-output-schema.json` exactly:

```json
{
  "business_problem": "We lose 30% of enterprise customers after year 1...",
  "domain": "saas",
  "constraint_summary": "CRM data, NPS scores, and support ticket history are available...",
  "ml_problems": [
    {
      "id": "prob_1",
      "name": "Churn Prediction",
      "description": "Predict which B2B accounts are at risk of churning within 90 days...",
      "category": "traditional",
      "engine": "autogluon",
      "autogluon_task_type": "binary_classification",
      "hypothesis_evidence": ["Accounts with NPS ≤ 2 churn at 84% vs 38% baseline"],
      "business_kpis": ["Reduce logo churn by 15% over two quarters"],
      "dataset": {
        "description": "Historical B2B SaaS account records with binary churn label.",
        "target_column": {
          "inferred_name": "churned",
          "type": "binary",
          "reason": "Binary churn outcome — direct target for binary_classification"
        },
        "source": {
          "s3_path": "s3://vforge-datasets/{session_id}/prob_1/dataset.csv",
          "row_count": null
        }
      }
    }
  ],
  "session_cost_usd": 0.12,
  "ready_for_experiments": true,
  "max_experiment_per_round": 3,
  "num_round": 3
}
```

### Read (Python)

```python
import json
import redis.asyncio as aioredis

async def get_session_output(session_id: str) -> dict | None:
    client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    async with client:
        raw = await client.get(f"vforge:conv:{session_id}")
    return json.loads(raw) if raw else None
```

### Read (CLI)

```bash
redis-cli GET "vforge:conv:f1050d64_622614c6_d172aafc"
```

---

## 2. Completion Stream (XADD → XREAD)

### Stream key

```
vforge:stream:conv_complete
```

### Event fields

| Field | Type | Example |
|-------|------|---------|
| `session_id` | string | `f1050d64_622614c6_d172aafc` |
| `event` | string | `conversation_complete` |
| `output_key` | string | `vforge:conv:f1050d64_622614c6_d172aafc` |
| `timestamp` | string | `2026-06-09T22:34:00+00:00` |

Use `output_key` to immediately `GET` the full JSON payload.

### Subscribe — blocking read from latest (Python)

```python
import json
import redis.asyncio as aioredis

STREAM = "vforge:stream:conv_complete"

async def listen_for_completions():
    client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    last_id = "$"  # only events that arrive after this subscribe call
    while True:
        entries = await client.xread({STREAM: last_id}, block=0, count=10)
        for _stream, messages in entries:
            for msg_id, fields in messages:
                last_id = msg_id
                raw = await client.get(fields["output_key"])
                payload = json.loads(raw)
                await handle_completed_session(fields["session_id"], payload)
```

### Consumer group — recommended for multi-instance deployments

```python
STREAM = "vforge:stream:conv_complete"
GROUP  = "orchestrator-workers"
WORKER = "worker-1"

# Create group once at startup (safe to call repeatedly)
try:
    await client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
except Exception:
    pass  # group already exists

# Processing loop
while True:
    entries = await client.xreadgroup(GROUP, WORKER, {STREAM: ">"}, block=0, count=1)
    for _stream, messages in entries:
        for msg_id, fields in messages:
            try:
                raw = await client.get(fields["output_key"])
                payload = json.loads(raw)
                await handle_completed_session(fields["session_id"], payload)
                await client.xack(STREAM, GROUP, msg_id)  # ack on success
            except Exception as exc:
                # Leave un-acked — redelivered automatically on next XREADGROUP
                print(f"Failed to process {msg_id}: {exc}")
```

---

## 3. Environment variable

| Variable | Value |
|----------|-------|
| `REDIS_URL` | `redis://localhost:6379` (local) |
| `REDIS_URL` | `rediss://your-cluster.cache.amazonaws.com:6379` (AWS ElastiCache TLS) |

---

## 4. Summary

```
SET  vforge:conv:{session_id}       TTL=7d    Full JSON (conv-output-schema.json)
XADD vforge:stream:conv_complete              One event per completed session
```

Both writes happen atomically in the same Redis connection when the user
confirms the final review step.
