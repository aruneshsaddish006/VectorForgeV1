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

## Dual-Engine Test — Churn Prediction + Retention Playbook Q&A

This is the primary end-to-end test. It maps a single business problem to **two sub-problems**,
triggering both **AutoGluon** (tabular binary classification) and **AutoRAG** (document Q&A) in one session.

**Files needed:**
- CSV: `backend/conversational/dataset/enriched_telecom_churn-2.csv`
- PDF: your ecommerce/retention playbook PDF

---

### Step 1 — Problem statement

```
We're a telecom operator with a serious subscriber retention problem. Every quarter we lose customers we could have saved, and our frontline retention agents waste hours digging through internal playbooks trying to find the right intervention scripts and offer guidelines.

I need two things: first, a model that predicts which customers are likely to churn so our retention team can reach out proactively. Second, a way for retention agents to instantly get answers from our customer success playbook — things like which discount to offer, when to escalate, what script to use for a Fiber vs DSL customer.
```

**Expected:** Agent replies with clarifying questions (`interrupt.type = "clarification"`)

---

### Step 2 — Answer clarifications

```
B2C telecom, ~10,000 active subscribers, mix of DSL and Fiber optic plans. We have a labeled historical CSV — 100 rows, 40 features covering tenure, contract type, usage trends, monthly charges, call drop rate, and channel engagement. The churn label column is called Churn (1 = churned, 0 = stayed). We also have a retention playbook PDF with intervention guides, offer tiers, and escalation scripts.
```

**Expected:** Agent confirms ML sub-problems (`interrupt.type = "sub_problem_confirmation"`) — **two** sub-problems:

1. **Churn Prediction** — `tabular_binary_classification` (AutoGluon) — CSV upload
2. **Retention Playbook Q&A** — `rag_question_answering` (AutoRAG) — PDF upload

---

### Step 3 — Confirm sub-problems

Click **Confirm** on the strategy card (or type):

```
confirmed
```

**Expected:** Agent asks how to source the dataset for **sub-problem 1** (Churn Prediction) —
`interrupt.type = "dataset_source_choice"`, `engine = "autogluon"`.

---

### Step 4a — Upload churn CSV (AutoGluon)

The `DataUploadCard` shows "Predictive · AutoGluon — upload training data".

Click **Upload file** and select:

```
backend/conversational/dataset/enriched_telecom_churn-2.csv
```

The file has 100 rows and 40 features: tenure, contract type, internet service, monthly charges,
usage trends, call drop rate, channel engagement (SMS/email/WhatsApp), and a `Churn` binary label.

**Expected:** Agent moves to `interrupt.type = "schema_confirmation"` for the CSV.

---

### Step 4b — Schema confirmation (CSV)

The agent should auto-detect `Churn` as the label column. Confirm with:

```
confirmed
```

To override the label column name if detection is wrong:

```
confirmed, label_column is Churn
```

**Expected:** Agent asks how to source the dataset for **sub-problem 2** (Retention Playbook Q&A) —
`interrupt.type = "dataset_source_choice"`, `engine = "autorag"`.

---

### Step 5 — Upload retention playbook PDF (AutoRAG)

The `DataUploadCard` shows "RAG · GenAI — upload document corpus" with file accept `.pdf,.csv`.

Click **Upload file** and select your ecommerce/retention playbook PDF.

**Expected:** Agent moves to `interrupt.type = "schema_confirmation"` (or skips to `final_review`
if no schema step is needed for RAG).

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

## Telecom Churn Only — Quick Single-Engine Test (uses enriched_telecom_churn-2.csv)

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

## Quick smoke test (no file uploads, end-to-end in ~2 min)

Use the dual-engine problem statement from Step 1 above, then use **skip** at both dataset upload
steps (Step 4a and Step 5), and **confirmed** at every other interrupt. Confirms the full graph
wires up without needing real files.

---

## Verify Redis write

```bash
redis-cli GET "vforge:conv:{your-session-id}"
```

The value should be valid JSON matching the structure in `conv-output-schema.json`.

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