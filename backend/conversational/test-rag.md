# RAG Workflow — End-to-End Test Guide

## Prerequisites

1. Start the conversational service:
   ```bash
   cd backend/conversational
   PYTHONPATH="$(cd .. && pwd)" uv run uvicorn conversational.main:app --reload --port 8001
   ```
2. Start the main backend (port 8000) and the frontend (`npm run dev`)
3. Log in and select (or create) a workspace + project so the session ID is set

---

## RAG Only — Document Q&A Test

This test covers a single **AutoRAG** sub-problem (`rag_question_answering`) triggered by a document-centric use case.

**Files needed:**
- PDF: your ecommerce/retention playbook PDF (or any document corpus PDF)

---

### Step 1 — Problem statement

```
Our frontline retention agents waste hours digging through our customer success playbook every day. I need a way for agents to instantly get answers from the playbook — things like which discount to offer, when to escalate, and what script to use for a Fiber vs DSL customer.
```

**Expected:** Agent replies with clarifying questions (`interrupt.type = "clarification"`)

---

### Step 2 — Answer clarifications

```
B2C telecom support team, ~50 agents. We have a PDF retention playbook covering intervention guides, offer tiers, and escalation scripts. Agents need to query it in natural language during live customer calls.
```

**Expected:** Agent confirms a single ML sub-problem (`interrupt.type = "sub_problem_confirmation"`):

1. **Retention Playbook Q&A** — `rag_question_answering` (AutoRAG) — PDF upload

---

### Step 3 — Confirm sub-problem

Click **Confirm** on the strategy card (or type):

```
confirmed
```

**Expected:** Agent asks how to source the dataset —
`interrupt.type = "dataset_source_choice"`, `engine = "autorag"`.

---

### Step 4 — Upload playbook PDF (AutoRAG)

The `DataUploadCard` shows "RAG · GenAI — upload document corpus" with file accept `.pdf,.csv`.

Click **Upload file** and select your retention playbook PDF.

**Expected:** Agent moves to `interrupt.type = "schema_confirmation"` (or skips to `final_review`
if no schema step is needed for RAG).

---

### Step 5 — Schema confirmation

If a schema confirmation interrupt appears, confirm with:

```
confirmed
```

**Expected:** Agent moves to `interrupt.type = "final_review"`.

---

### Step 6 — Final review

```
confirmed
```

**Expected:**

- Session status becomes `complete`
- Redis key `vforge:conv:{sessionId}` is written
- UI shows: *"Experiment plan ready — session `{id}` output written to Redis. Orchestrators can now consume it."*

---

## Quick smoke test (no file upload, ~1 min)

Use the problem statement from Step 1 above, then use **skip** at the dataset upload step (Step 4),
and **confirmed** at every other interrupt. Confirms the RAG graph wires up without needing a real file.

---

## Verify Redis write

```bash
redis-cli GET "vforge:conv:{your-session-id}"
```

The value should be valid JSON with a single `rag_question_answering` sub-problem matching the structure in `conv-output-schema.json`.

---

## Interrupt type reference

| `interrupt.type`           | What it means                          | What to send                                      |
| -------------------------- | -------------------------------------- | ------------------------------------------------- |
| `clarification`            | Agent needs more business context      | Free-text answer(s)                               |
| `sub_problem_confirmation` | Review ML problems the agent mapped    | `confirmed` or `Yes, confirmed`                   |
| `dataset_source_choice`    | How to supply the dataset              | `upload`, `discover`, or `skip`                   |
| `awaiting_upload`          | Graph waiting for a file               | Use the paperclip button to attach a PDF          |
| `exa_results_review`       | Pick a public dataset from results     | `0` (index of chosen result)                      |
| `schema_confirmation`      | Confirm inferred column names          | `confirmed`                                       |
| `final_review`             | Final sign-off before Redis is written | `confirmed`                                       |
