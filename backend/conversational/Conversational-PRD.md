# VectorForge Conversational Agent — PRD

**Module:** `conversational/`
**Scope:** Intake layer bridging natural language business problems to structured ML experiment configs

---

## 1. Purpose

The conversational agent is VectorForge's front door. A user describes a business problem in plain English; the agent decomposes it into scoped, evidenced ML sub-problems, sources or accepts datasets per sub-problem, and emits a structured payload that downstream experiment engines (AutoGluon, AutoRAG) consume directly.

**Supported experiment engines:**
- **AutoGluon** — tabular, text, image, multimodal classification/regression/forecasting
- **AutoRAG** — RAG pipeline optimisation for QA and retrieval problems

---

## 2. System Architecture

```
POST /conversations
        │
        ▼
┌──────────────────┐
│   intake_node    │  Extract business problem, ask clarifying questions
│                  │  INTERRUPT if context insufficient
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│   decomposer_node    │  Dual-lens scoping (business + DS lens)
│                      │  Constraint audit (data/infra/privacy)
│                      │  Hypothesis generation + lightweight validation
│                      │  Map validated problems to ML sub-problems
│                      │  Infer target/label/timestamp columns per task type
│                      │  INTERRUPT: confirm sub-problems + inferred columns
└────────┬─────────────┘
         │
         ▼
┌──────────────────────────┐
│  dataset_sourcing_node   │  Per sub-problem: show dataset schema requirements
│  (sequential loop)       │  INTERRUPT: choose upload / Exa discover / skip
│                          │  upload → S3 via interrupt/resume pattern
│                          │  discover → Exa search → INTERRUPT: approve cost
│                          │  INTERRUPT: confirm actual schema + column mapping
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────┐
│  output_compiler_node│  Assemble mandatory final payload
│                      │  INTERRUPT: final review before handoff
└────────┬─────────────┘
         │
         ▼
        END — structured JSON payload consumed by experiment engines
```

---

## 3. Problem Categories

### Traditional (AutoGluon)

| Category | AutoGluon Task | Inferred Columns | Business Examples |
|---|---|---|---|
| `tabular_binary_classification` | binary_classification | `label_column` (binary) | Churn, fraud, lead scoring |
| `tabular_multiclass_classification` | multiclass_classification | `label_column`, `class_labels[]` | Ticket category, intent |
| `tabular_regression` | regression | `label_column` (continuous) | Revenue, LTV, price |
| `time_series_forecasting` | time_series_forecasting | `target_column`, `timestamp_column`, `item_id_column` | Demand, inventory |
| `text_classification` | multimodal/text | `text_column`, `label_column` | Sentiment, ticket routing |
| `image_classification` | multimodal/image | `image_path_column`, `label_column` | Visual inspection |

### GenAI (AutoRAG)

| Category | AutoRAG Task | Required Files | Business Examples |
|---|---|---|---|
| `rag_question_answering` | QA pipeline | corpus (`doc_id`, `contents`); QA eval (`qid`, `query`, `retrieval_gt`, `generation_gt`) | Support deflection, policy QA |
| `rag_document_retrieval` | Retrieval pipeline | corpus (`doc_id`, `contents`); queries (`qid`, `query`, `retrieval_gt`) | Semantic search, KB lookup |

---

## 4. API Endpoints

```
POST   /conversations                           Start conversation
POST   /conversations/{id}/respond              Resume after interrupt (text/approval/choice)
POST   /conversations/{id}/upload-dataset       Upload file to S3 for a sub-problem (triggers resume)
GET    /conversations/{id}                      Current state + pending interrupt
GET    /conversations/{id}/output               Final structured output (when complete)
DELETE /conversations/{id}                      Delete conversation + S3 artifacts
```

---

## 5. Interrupt Types

| Type | When | Resume payload |
|---|---|---|
| `clarification` | Intake: missing critical info | `{"answers": {"domain": "saas", "scale": "500 accounts/month"}}` |
| `sub_problem_confirmation` | After decomposition | `{"confirmed": true, "column_overrides": {"prob_1": {"label_column": "is_churn"}}}` |
| `dataset_source_choice` | Per sub-problem | `{"choice": "upload"\|"discover"\|"skip", "prob_id": "prob_1"}` |
| `dataset_cost_approval` | Exa search cost estimate | `{"approved": true, "query": "B2B SaaS churn dataset ARR NPS"}` |
| `schema_confirmation` | After dataset ready | `{"confirmed": true, "column_overrides": {"label_column": "churned"}}` |
| `final_review` | Output compiled | `{"confirmed": true}` |

---

## 6. Mandatory Output Schema

```json
{
  "session_id": "sess_abc123",
  "status": "ready_for_experiments",
  "business_problem": "We are losing 40% of enterprise accounts after year 1. We need to predict who is at risk and personalise win-back outreach.",
  "domain": "saas",
  "constraint_summary": {
    "narrative": "The business has CRM data, support ticket history, and NPS scores available, which provides sufficient signal for a churn prediction model. Clickstream and product usage telemetry are not yet instrumented, ruling out granular feature engineering. Email outreach via Mailchimp is available for win-back campaigns. No regulatory blockers identified for the data in scope.",
    "dropped_problems": [
      {
        "name": "Product Usage Anomaly Detection",
        "reason": "Product telemetry/event stream is not currently instrumented. No feature data available to build this model."
      }
    ]
  },
  "ml_problems": [
    {
      "id": "prob_1",
      "name": "Churn Prediction",
      "description": "Predict which B2B accounts are at risk of churning within 90 days of their renewal date, using ARR, NPS, support ticket volume, and contract age as signals.",
      "category": "traditional",
      "engine": "autogluon",
      "autogluon_task_type": "binary_classification",
      "hypothesis_evidence": [
        "Accounts with NPS score <= 2 show 84% churn rate vs 38% baseline — strong signal (chi-sq p=0.0001)",
        "Accounts with >20 support tickets/month churn at 71% — strong signal (lift=1.87)"
      ],
      "business_kpis": [
        "Reduce logo churn by 15% over two quarters",
        "Flag at-risk accounts 90 days before renewal to enable proactive intervention"
      ],
      "dataset": {
        "description": "Historical B2B SaaS account records with a binary churn outcome label. Each row represents one account over a measurement period. Minimum required columns: account identifier, ARR or revenue metric, NPS score, support ticket count, and a binary churn label. At least 500 rows needed for reliable model training.",
        "inferred_columns": {
          "label_column": {
            "inferred_name": "churned",
            "type": "binary",
            "confidence": "high",
            "reason": "Binary churn outcome directly maps to target variable for binary_classification task"
          }
        },
        "user_confirmed_columns": {
          "label_column": "churned"
        },
        "min_rows": 500,
        "source": {
          "type": "discovered",
          "s3_path": "s3://vforge-datasets/sess_abc123/prob_1/dataset.csv",
          "row_count": 4820,
          "feature_count": 14,
          "quality_score": 92,
          "source_description": "B2B SaaS churn dataset sourced via Exa from public repositories. Includes firmographics, ARR, NPS, support volume, and binary churn label.",
          "actual_schema": [
            {"column": "company", "type": "string", "null_pct": 0, "source": "Exa"},
            {"column": "arr_usd", "type": "number", "null_pct": 2, "source": "Exa"},
            {"column": "employee_count", "type": "integer", "null_pct": 0, "source": "Exa"},
            {"column": "nps_score", "type": "number", "null_pct": 8, "source": "Enriched"},
            {"column": "support_tickets", "type": "integer", "null_pct": 4, "source": "Enriched"},
            {"column": "churned", "type": "boolean", "null_pct": 0, "source": "Exa"}
          ]
        }
      }
    },
    {
      "id": "prob_2",
      "name": "Support Query Deflection",
      "description": "Build a RAG pipeline that answers common support questions from a knowledge base corpus, reducing the proportion of tickets that require human resolution.",
      "category": "genai",
      "engine": "autorag",
      "autogluon_task_type": null,
      "hypothesis_evidence": [
        "200 support tickets/day at $8/ticket = $584K/year — significant cost reduction opportunity",
        "Existing knowledge base corpus is available — RAG directly feasible without data collection"
      ],
      "business_kpis": [
        "Deflect 30% of inbound support tickets to automated responses",
        "Reduce average cost per support interaction from $8 to under $3"
      ],
      "dataset": {
        "description": "AutoRAG requires two files: (1) a corpus file containing your knowledge base documents — each row is one document with a unique ID and its text content; (2) a QA evaluation file with a sample of real support queries paired with ground-truth answers, used to benchmark retrieval and generation quality. The corpus is your existing KB; the QA file should be sampled from resolved tickets.",
        "inferred_columns": {
          "corpus": {
            "doc_id_column": {"inferred_name": "doc_id", "confidence": "high", "reason": "AutoRAG standard corpus schema"},
            "content_column": {"inferred_name": "contents", "confidence": "high", "reason": "AutoRAG standard corpus schema"}
          },
          "qa_eval": {
            "query_id_column": {"inferred_name": "qid", "confidence": "high", "reason": "AutoRAG standard QA eval schema"},
            "query_column": {"inferred_name": "query", "confidence": "high", "reason": "AutoRAG standard QA eval schema"},
            "retrieval_gt_column": {"inferred_name": "retrieval_gt", "confidence": "high", "reason": "List of relevant doc_ids for retrieval eval"},
            "generation_gt_column": {"inferred_name": "generation_gt", "confidence": "high", "reason": "Expected answer text for generation eval"}
          }
        },
        "user_confirmed_columns": {
          "corpus_doc_id_column": "doc_id",
          "corpus_content_column": "contents",
          "qa_query_column": "query",
          "qa_generation_gt_column": "answer_text"
        },
        "min_rows": 100,
        "source": {
          "type": "uploaded",
          "corpus_s3_path": "s3://vforge-datasets/sess_abc123/prob_2/corpus.csv",
          "qa_s3_path": "s3://vforge-datasets/sess_abc123/prob_2/qa_eval.csv",
          "corpus_row_count": 850,
          "qa_row_count": 120,
          "quality_score": 88,
          "source_description": "User uploaded: existing help centre articles as corpus, 120 resolved tickets sampled as QA eval"
        }
      }
    }
  ],
  "session_cost_usd": 0.12,
  "ready_for_experiments": true
}
```

---

## 7. Column Inference Rules per Task Type

| Task Type | Inferred Columns | User Confirmation Required |
|---|---|---|
| binary_classification | `label_column` | Yes — confirm column name |
| multiclass_classification | `label_column`, `class_labels[]` | Yes — confirm column + class list |
| regression | `label_column` (continuous) | Yes — confirm column name |
| time_series_forecasting | `target_column`, `timestamp_column`, `item_id_column` | Yes — all three |
| text_classification | `text_column`, `label_column` | Yes — both |
| image_classification | `image_path_column`, `label_column` | Yes — both |
| rag_question_answering | corpus: `doc_id`+`contents`; QA: `qid`+`query`+`retrieval_gt`+`generation_gt` | Yes — map if schema differs |
| rag_document_retrieval | corpus: `doc_id`+`contents`; queries: `qid`+`query`+`retrieval_gt` | Yes — map if schema differs |

---

## 8. LangGraph Runtime

```yaml
graph_type: StateGraph
checkpointer: AsyncSqliteSaver  # file: conversations.db
thread_id: session_id
human_in_the_loop: langgraph interrupt()
file_upload_pattern: |
  1. graph.interrupt({type: dataset_source_choice})
  2. client POSTs file to /conversations/{id}/upload-dataset
  3. server uploads file to S3, gets s3_path
  4. server resumes graph: Command(resume={choice: upload, s3_path: ...})
parallelism: sequential  # one sub-problem sourced at a time in conversation
```

---

## 9. File Structure

```
conversational/
├── PRD.md
├── __init__.py
├── main.py                      FastAPI app entry point
├── config.py                    Settings (env vars)
├── models/
│   ├── __init__.py
│   ├── schemas.py               Pydantic request/response models
│   └── problem_taxonomy.yaml    ML problem type definitions
├── services/
│   ├── __init__.py
│   ├── llm.py                   Anthropic wrapper with structured output
│   ├── s3.py                    S3 file upload service
│   └── exa_search.py            Exa dataset discovery
├── graph/
│   ├── __init__.py
│   ├── state.py                 ConversationalState TypedDict
│   ├── checkpointer.py          AsyncSqliteSaver setup
│   ├── graph.py                 StateGraph assembly
│   └── nodes/
│       ├── __init__.py
│       ├── intake.py            Business problem intake + clarification
│       ├── decomposer.py        Problem decomposer (dual lens + constraints + routing)
│       ├── dataset_sourcing.py  Dataset sourcing loop (upload/discover/skip)
│       └── output_compiler.py   Final payload assembly
└── api/
    ├── __init__.py
    └── routes.py                FastAPI route handlers
```

---

## 10. Scope

**In scope:**
- Conversational intake with multi-turn clarification
- Problem decomposition → traditional (AutoGluon) + GenAI (AutoRAG) only
- Column inference + user confirmation at decomposition and schema stages
- Dataset sourcing: S3 upload or Exa discovery (Kaggle/public datasets)
- Stateful LangGraph graph with SQLite checkpointing
- FastAPI REST API with interrupt/resume pattern

**Out of scope:**
- Technical KPI weighting (handled by downstream AutoGluon/AutoRAG orchestrator)
- Multi-tenant user management or billing
- AutoML execution (handled by downstream engines)
- Frontend rendering (API only — UI consumes interrupt payloads)
