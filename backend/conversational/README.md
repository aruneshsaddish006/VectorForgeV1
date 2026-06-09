# VectorForge Conversational API

Stateful LangGraph API that turns a natural-language business problem into a structured AutoGluon / AutoRAG experiment plan.

---

## Setup

```bash
cd VectorForge/conversational

# 1. Copy env template and fill in real values
cp .env.example .env

# 2. Create virtual environment (uses Python 3.11 from .python-version)
uv venv

# 3. Install dependencies
uv sync

# 4. (Optional) install dev tools
uv sync --group dev

# 5. Start the server
uv run uvicorn conversational.main:app --reload --port 8000
```

**Required `.env` values before first run:**

| Key | Where to get it |
|-----|----------------|
| `AI_GATEWAY_API_KEY` | Vercel dashboard → AI Gateway |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS IAM |
| `S3_BUCKET_NAME` | Your S3 bucket name |
| `DB_HOST` / `DB_PASSWORD` | AWS RDS instance |
| `EXA_API_KEY` | [exa.ai](https://exa.ai) dashboard |

Health check — confirm the server is up:

```bash
curl http://localhost:8000/health
# {"status":"ok","graph_ready":true}
```

---

## Full Conversation Flow

The API is interrupt-driven. Every step returns either an `interrupt` (needs your input) or a `final_output` (done).

### Step 1 — Start a session

```bash
curl -s -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "message": "We lose 40% of enterprise accounts after year 1. Need to flag at-risk accounts 90 days before renewal and deflect common support queries to cut our $8/ticket cost."
  }' | jq .
```

**Response:**
```json
{
  "data": {
    "session_id": "3f2a1b4c-...",
    "status": "intake",
    "interrupt": {
      "type": "clarification",
      "questions": ["What industry are you in?", "How many accounts do you have?"],
      "missing_fields": ["domain", "scale_description"]
    }
  }
}
```

Save the session ID:
```bash
SESSION="3f2a1b4c-..."   # paste your session_id here
```

---

### Step 2 — Answer clarifying questions

```bash
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{
    "response": {
      "message": "B2B SaaS, 500 enterprise accounts, ~$50K ARR each",
      "answers": {
        "domain": "saas",
        "scale_description": "500 enterprise accounts, $50K ARR average"
      }
    }
  }' | jq .
```

Repeat until `interrupt.type` becomes `"sub_problem_confirmation"`.

---

### Step 3 — Confirm ML sub-problems

The decomposer has mapped your problem to ML tasks. Review and confirm:

```bash
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"confirmed": true}}' | jq .
```

To override an inferred column name before confirming:
```json
{
  "response": {
    "confirmed": true,
    "column_overrides": {
      "prob_1": {"label_column": "is_churned"}
    }
  }
}
```

---

### Step 4 — Source datasets (once per problem)

For each sub-problem, `interrupt.type = "dataset_source_choice"`.

**Option A — Upload a file:**

```bash
# Tell the graph you'll upload
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"choice": "upload"}}' | jq .

# Upload the file — graph resumes automatically after S3 upload
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/upload-dataset \
  -F "problem_id=prob_1" \
  -F "file=@/path/to/churn_data.csv" | jq .
```

**Option B — Discover from Kaggle / public datasets:**

```bash
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"choice": "discover"}}' | jq .

# Pick from the Exa search results by index
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"selected_index": 0}}' | jq .
```

**Option C — Skip:**

```bash
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"choice": "skip"}}' | jq .
```

After each dataset, confirm the inferred column mapping:

```bash
# Accept inferred columns as-is
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"confirmed": true, "column_overrides": {}}}' | jq .

# Or override a specific column name
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"confirmed": true, "column_overrides": {"label_column": "churned_flag"}}}' | jq .
```

---

### Step 5 — Final review

When all datasets are sourced, `interrupt.type = "final_review"`. The response includes a preview of `final_output`:

```bash
# Confirm — marks session complete
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"confirmed": true}}' | jq .

# Or regenerate the decomposition
curl -s -X POST http://localhost:8000/api/v1/conversations/$SESSION/respond \
  -H "Content-Type: application/json" \
  -d '{"response": {"regenerate": true}}' | jq .
```

---

### Step 6 — Fetch the orchestrator payload

```bash
curl -s http://localhost:8000/api/v1/conversations/$SESSION/final-output | jq .
```

Pass `data` directly to your AutoGluon / AutoRAG orchestrator agent.

---

## Check session state at any time

```bash
curl -s http://localhost:8000/api/v1/conversations/$SESSION | jq .
```

Returns `status`, full `messages[]` history, current `interrupt` (if paused), and `final_output` (if complete).

---

## Interrupt type reference

| `interrupt.type` | What it means | Resume key |
|---|---|---|
| `clarification` | Needs more business context | `{"answers": {...}}` |
| `sub_problem_confirmation` | Review ML problems mapped | `{"confirmed": true}` |
| `dataset_source_choice` | How to supply dataset | `{"choice": "upload\|discover\|skip"}` |
| `awaiting_upload` | Graph waiting for file upload | Use `/upload-dataset` endpoint |
| `exa_results_review` | Pick a public dataset | `{"selected_index": 0}` |
| `schema_confirmation` | Confirm column names | `{"confirmed": true, "column_overrides": {}}` |
| `final_review` | Final sign-off | `{"confirmed": true}` |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `503 Graph not yet initialised` | Server still starting — retry in a moment |
| `502 S3 upload failed` | Check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` in `.env` |
| `409 Conversation not yet complete` | Session not at `status: complete` — check current interrupt |
| `404 Session not found` | Wrong session ID, or Postgres lost state on restart |
| LLM returns empty | Check `AI_GATEWAY_API_KEY` and `LLM_MODEL` in `.env` |
| Postgres connection refused | Check `DB_HOST`, `DB_PORT`, `DB_PASSWORD`; confirm RDS security group allows your IP |
