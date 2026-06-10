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

## Telecom Churn — Quick Test (uses enriched_telecom_churn-2.csv)

### Step 1 — Problem statement

```
We're a telecom operator losing subscribers every quarter. I need to predict which customers are about to churn so retention teams can intervene before it happens.
```

### Step 2 — Clarifications

```
B2C telecom, ~10,000 active subscribers, mix of DSL and Fiber optic plans. We have a labeled historical CSV with account features, usage metrics, and channel engagement data. Label column is Churn (0 = stayed, 1 = churned).
```

### Step 3 — Confirm sub-problems

Click **Confirm**. Expected: one sub-problem — `tabular_binary_classification` (AutoGluon).

### Step 4 — Upload dataset

Click **Upload file** and select:

```
backend/conversational/dataset/enriched_telecom_churn-2.csv
```

The file has 100 rows and 40 features including tenure, contract type, internet service, monthly charges, usage trends, call drop rate, channel engagement (SMS/email/WhatsApp), and a `Churn` binary label.

### Step 5 — Schema confirmation

The agent should auto-detect `Churn` as the label column. Confirm with:

```
confirmed
```

### Step 6 — Final review

```
confirmed
```

**Expected:** Session completes, Redis key written with the AutoGluon experiment plan.

---

## Step-by-step chat queries

### Step 1 — Start the conversation

Type a business problem and hit Enter:

```
We lose 30% of enterprise customers after year 1. I need to predict which accounts will churn 90 days before renewal AND enable our customer success team to instantly answer questions from our support documentation and account health reports.
```

**Expected:** Agent replies with clarifying questions (`interrupt.type = "clarification"`)

---

### Step 2 — Answer clarifications

Answer the questions in one message:

```
B2B SaaS, 400 enterprise accounts, average $45K ARR, North America market. We have historical account CSVs and a support knowledge base of ~200 PDF documents.
```

**Expected:** Agent confirms ML sub-problems (`interrupt.type = "sub_problem_confirmation"`) — **two** sub-problems:
1. **Churn Prediction** — `tabular_binary_classification` (AutoGluon) — CSV upload
2. **Support KB Q&A** — `rag_question_answering` (AutoRAG) — PDF/CSV corpus upload

---

### Step 3 — Confirm sub-problems

Click **Confirm** on the strategy card (or type):

```
Yes, confirmed
```

**Expected:** Agent asks how to source the dataset for **sub-problem 1** (Churn Prediction) — `interrupt.type = "dataset_source_choice"`, `engine = "autogluon"`.

---

### Step 4a — Churn Prediction dataset (AutoGluon — CSV)

The `DataUploadCard` shows "Predictive · AutoGluon — upload training data".

**Option A — upload a CSV** (click Upload file, pick a CSV with account features + churn label):

Click the **Upload file** button and select a `.csv` or `.parquet` file.

**Option B — skip (fastest for testing):**

```
skip
```

**Option C — discover from web:**

```
discover
```

Then when Exa results appear (`interrupt.type = "exa_results_review"`), pick index `0`.

---

### Step 4b — Support KB Q&A dataset (AutoRAG — PDF or CSV corpus)

After the first problem completes, the agent immediately asks for the **second** sub-problem dataset — `interrupt.type = "dataset_source_choice"`, `engine = "autorag"`.

The `DataUploadCard` shows "RAG · GenAI — upload document corpus" with file accept `.pdf,.csv`.

**Option A — upload a PDF or CSV corpus:**

Click the **Upload file** button and select a `.pdf` document or a `.csv` corpus file.

**Option B — skip:**

```
skip
```

---

### Step 5 — Confirm column schemas

For each uploaded dataset (`interrupt.type = "schema_confirmation"`):

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

To confirm the API wires up end-to-end in under 2 minutes, use **skip** at both Step 4a and 4b, then **confirmed** at every other interrupt.

---

## Interrupt type reference

| `interrupt.type`           | What it means                          | What to send                                      |
| -------------------------- | -------------------------------------- | ------------------------------------------------- |
| `clarification`            | Agent needs more business context      | Free-text answer(s)                               |
| `sub_problem_confirmation` | Review ML problems the agent mapped    | `confirmed` or `Yes, confirmed`                   |
| `dataset_source_choice`    | How to supply the dataset              | `upload`, `discover`, or `skip`                   |
| `awaiting_upload`          | Graph waiting for a file               | Use the paperclip button to attach a CSV or PDF   |
| `exa_results_review`       | Pick a public dataset from results     | `0` (index of chosen result)                      |
| `schema_confirmation`      | Confirm inferred column names          | `confirmed` or `confirmed, label_column is <col>` |
| `final_review`             | Final sign-off before Redis is written | `confirmed`                                       |