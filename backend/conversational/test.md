# Conversational Endpoint — End-to-End Test Guide

## Prerequisites

1. Start the conversational service:
   ```bash
   cd backend/conversational
   PYTHONPATH="$(cd .. && pwd)" uv run uvicorn conversational.main:app --reload --port 8001
   ```
2. Start the main backend (port 8000) and the frontend (`npm run dev`)
3. Log in and select (or create) a workspace + project so the session ID is set

---

## Step-by-step chat queries

### Step 1 — Start the conversation

Type a business problem and hit Enter:

```
We lose 30% of enterprise customers after year 1. I need to predict which accounts will churn 90 days before renewal.
```

**Expected:** Agent replies with clarifying questions (`interrupt.type = "clarification"`)

---

### Step 2 — Answer clarifications

Answer the questions in one message:

```
B2B SaaS, 400 enterprise accounts, average $45K ARR, North America market
```

**Expected:** Agent confirms ML sub-problems (`interrupt.type = "sub_problem_confirmation"`) — a churn classification task

---

### Step 3 — Confirm sub-problems

```
Yes, confirmed
```

**Expected:** Agent asks how to source a dataset (`interrupt.type = "dataset_source_choice"`)

---

### Step 4 — Choose data source

Pick one of these depending on what you want to test:

**Option A — skip (fastest for testing):**

```
skip
```

**Option B — discover from web:**

```
discover
```

Then when Exa results appear (`interrupt.type = "exa_results_review"`):

```
0
```

*(picks the first result)*

**Option C — upload a file:**

```
upload
```

Then use the paperclip button in the composer to attach a CSV file.

---

### Step 5 — Confirm column schema

After the dataset is sourced (`interrupt.type = "schema_confirmation"`):

```
confirmed
```

Or to override a column name:

```
confirmed, label_column is churned_flag
```

---

### Step 6 — Final review

When all problems are processed (`interrupt.type = "final_review"`):

```
confirmed
```

**Expected:**

- Session status becomes `complete`
- Redis key `vforge:conv:{sessionId}` is written
- UI shows: *"Experiment plan ready — session `{id}` output written to Redis. Orchestrators can now consume it."*

---

## Verify Redis write

```bash
redis-cli GET "vforge:conv:{your-session-id}"
```

The value should be valid JSON matching the structure in `conv-output-schema.json`.

---

## Quick smoke test

To confirm the API wires up end-to-end in under 2 minutes, use **skip** at Step 4 and **confirmed** at every other interrupt.

---

## Interrupt type reference

| `interrupt.type`           | What it means                          | What to send                                      |
| -------------------------- | -------------------------------------- | ------------------------------------------------- |
| `clarification`            | Agent needs more business context      | Free-text answer(s)                               |
| `sub_problem_confirmation` | Review ML problems the agent mapped    | `confirmed` or `Yes, confirmed`                   |
| `dataset_source_choice`    | How to supply the dataset              | `upload`, `discover`, or `skip`                   |
| `awaiting_upload`          | Graph waiting for a file               | Use the paperclip button to attach a CSV          |
| `exa_results_review`       | Pick a public dataset from results     | `0` (index of chosen result)                      |
| `schema_confirmation`      | Confirm inferred column names          | `confirmed` or `confirmed, label_column is <col>` |
| `final_review`             | Final sign-off before Redis is written | `confirmed`                                       |