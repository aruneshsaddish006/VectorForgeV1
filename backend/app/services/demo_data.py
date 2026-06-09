from __future__ import annotations

from typing import Any
from uuid import uuid4


EFFORTS = [
    {"value": "low", "label": "Quick Draft", "cost": "~$0.025", "description": "Prototype, small datasets"},
    {"value": "medium", "label": "Standard", "cost": "~$0.10", "description": "Most production use cases"},
    {"value": "high", "label": "Deep Research", "cost": "~$0.50", "description": "Large, richly enriched"},
    {"value": "xhigh", "label": "Exhaustive", "cost": "~$1.00", "description": "Enterprise-grade research"},
]

DATA_SOURCE_PATHS = [
    {
        "id": "upload",
        "title": "Upload my data",
        "bestFor": "You already have labelled data",
        "input": "CSV, Excel, PDF, DOCX, or DB connection",
        "time": "~30 sec validation",
        "cost": "No credits used",
        "output": "Validated typed schema",
    },
    {
        "id": "exa",
        "title": "Build dataset from web",
        "bestFor": "You have no training data",
        "input": "Natural language query",
        "time": "1-6 min build",
        "cost": "From $0.025 / run",
        "output": "Schema-validated JSON with provenance",
    },
    {
        "id": "hybrid",
        "title": "Enrich my data",
        "bestFor": "You have seed rows and need web-sourced columns",
        "input": "Seed CSV plus web enrichment",
        "time": "2-8 min build",
        "cost": "From $0.10 / run",
        "output": "Merged enriched dataset",
    },
]

SCHEMA_COLUMNS = [
    {"name": "company", "type": "string", "nullPct": 0, "sample": "Northwind SaaS", "source": "exa"},
    {"name": "arr_usd", "type": "number", "nullPct": 2, "sample": "4,200,000", "source": "exa"},
    {"name": "employee_count", "type": "integer", "nullPct": 0, "sample": "180", "source": "exa"},
    {"name": "nps_score", "type": "number", "nullPct": 8, "sample": "41", "source": "enriched"},
    {"name": "support_tickets", "type": "integer", "nullPct": 4, "sample": "312", "source": "enriched"},
    {"name": "churned", "type": "boolean", "nullPct": 0, "sample": "false", "source": "exa"},
]

PREVIEW_ROWS = [
    {"company": "Northwind SaaS", "arr": "4.2M", "emp": 180, "nps": 41, "tickets": 312, "churned": False},
    {"company": "Lumen Analytics", "arr": "1.1M", "emp": 64, "nps": 28, "tickets": 540, "churned": True},
    {"company": "Cedar Cloud", "arr": "8.9M", "emp": 420, "nps": 53, "tickets": 211, "churned": False},
    {"company": "Pivot Metrics", "arr": "2.4M", "emp": 96, "nps": 19, "tickets": 690, "churned": True},
    {"company": "Atlas Stack", "arr": "6.0M", "emp": 250, "nps": 47, "tickets": 180, "churned": False},
]

DEMO_WORKSPACE: dict[str, Any] = {
    "workspace": {"id": "ws_demo", "name": "Acme Corp", "plan": "Enterprise plan"},
    "problem": {
        "statement": "We're losing enterprise customers and can't predict who's about to churn.",
        "kpis": ["Reduce logo churn by 15% over two quarters", "Flag at-risk accounts 90 days before renewal"],
        "intent": "classification",
        "taskType": "Classification",
    },
    "strategy": {
        "summary": "I recommend a churn prediction model as the primary use case, supported by expansion propensity and support deflection RAG.",
        "metrics": [
            {"label": "Use cases mapped", "value": "3", "tone": "primary"},
            {"label": "Projected 12-mo ROI", "value": "$1.4M", "tone": "success", "hint": "Blended estimate"},
            {"label": "Feasibility", "value": "High", "tone": "success", "hint": "Data available"},
        ],
        "useCases": [
            {"name": "Churn Prediction", "type": "Classification", "confidence": "High", "roi": "+$1.2M ARR retained"},
            {"name": "Expansion Propensity", "type": "Regression", "confidence": "Medium", "roi": "+18% upsell rate"},
            {"name": "Support Deflection RAG", "type": "Retrieval", "confidence": "High", "roi": "-32% ticket volume"},
        ],
    },
    "dataSources": DATA_SOURCE_PATHS,
    "exaRun": {
        "id": "exa_run_demo",
        "datasetId": "saas_churn_v2",
        "query": "Build a labelled churn dataset for B2B SaaS companies, 50-500 employees, with ARR, NPS, support ticket volume, and churn label.",
        "efforts": EFFORTS,
        "selectedEffort": "medium",
        "status": "complete",
        "stages": ["Queued", "Running", "Enriching rows", "Validating schema", "Complete"],
        "activeStage": 4,
        "stats": {"rows": "180", "features": "12", "qualityScore": "92", "runCost": "$0.10"},
        "previewRows": PREVIEW_ROWS,
        "provenance": [
            {"field": "arr_usd", "src": "crunchbase.com/northwind-saas"},
            {"field": "nps_score", "src": "g2.com/products/northwind/reviews"},
            {"field": "support_tickets", "src": "trustpilot.com/review/northwind"},
        ],
    },
    "dataset": {
        "id": "saas_churn_v2",
        "name": "saas_churn_v2",
        "rowCount": 180,
        "columnCount": 6,
        "taskType": "Classification",
        "qualityScore": 92,
        "targetColumn": "churned",
        "columns": SCHEMA_COLUMNS,
        "issues": [
            {"field": "nps_score", "message": "8% nulls. The agent can impute with the median or drop affected rows."}
        ],
    },
    "training": {
        "id": "train_demo",
        "status": "complete",
        "metrics": {"bestRocAuc": "0.921", "modelsTrained": "11", "trainTime": "6m 24s", "computeCost": "$0.64"},
        "leaderboard": [
            {"rank": 1, "model": "WeightedEnsemble_L2", "metric": 0.921, "inferTime": "12ms", "best": True},
            {"rank": 2, "model": "LightGBM_BAG_L1", "metric": 0.908, "inferTime": "4ms"},
            {"rank": 3, "model": "CatBoost_BAG_L1", "metric": 0.903, "inferTime": "6ms"},
            {"rank": 4, "model": "XGBoost_BAG_L1", "metric": 0.897, "inferTime": "5ms"},
            {"rank": 5, "model": "RandomForest_BAG_L1", "metric": 0.882, "inferTime": "9ms"},
        ],
        "featureImportance": [
            {"f": "nps_score", "w": 0.34},
            {"f": "support_tickets", "w": 0.27},
            {"f": "arr_usd", "w": 0.19},
            {"f": "employee_count", "w": 0.12},
        ],
    },
    "rag": {
        "id": "rag_demo",
        "status": "complete",
        "metrics": {"faithfulness": "0.94", "contextRecall": "0.89", "trialsRun": "24", "p95Latency": "640ms"},
        "pipeline": [
            {"stage": "Parse", "detail": "PDF + web corpus", "value": "1,204 docs"},
            {"stage": "Chunk", "detail": "Semantic, 512 tokens", "value": "8,930 chunks"},
            {"stage": "QA Gen", "detail": "Synthetic eval set", "value": "320 pairs"},
            {"stage": "Optimize", "detail": "Trial sweep", "value": "24 configs"},
        ],
        "bestConfig": [
            {"k": "Retriever", "v": "hybrid (BM25 + dense)"},
            {"k": "Embedding", "v": "text-embedding-3-large"},
            {"k": "Reranker", "v": "cohere-rerank-v3"},
            {"k": "Top-k", "v": "6"},
            {"k": "Chunk size", "v": "512 / 64 overlap"},
        ],
    },
    "activity": [
        {"id": "a7", "agent": "Billing Agent", "message": "Awaiting Stripe charge approval - $1.94", "time": "now", "status": "waiting-approval", "tool": "Stripe API", "cost": "$1.94", "detail": "Pay-per-use overage on Pro plan."},
        {"id": "a6", "agent": "RAG Agent", "message": "Completed 24 pipeline trials", "time": "2m ago", "status": "complete", "tool": "AutoRAG", "detail": "Best config: hybrid retriever + cohere rerank."},
        {"id": "a5", "agent": "Training Agent", "message": "AutoGluon job finished - ROC-AUC 0.921", "time": "8m ago", "status": "complete", "tool": "SageMaker", "cost": "$0.64"},
        {"id": "a4", "agent": "Data Agent", "message": "Dataset schema confirmed by approver", "time": "12m ago", "status": "complete", "tool": "S3"},
        {"id": "a3", "agent": "Data Agent", "message": "Exa run completed - 180 rows validated", "time": "15m ago", "status": "complete", "tool": "Exa Agent API", "cost": "$0.10", "detail": "Grounding citations stored for 6 fields."},
    ],
}


def make_exa_run(payload: dict[str, Any]) -> dict[str, Any]:
    run = dict(DEMO_WORKSPACE["exaRun"])
    run["id"] = f"exa_run_{uuid4().hex[:8]}"
    run["query"] = payload.get("query") or run["query"]
    run["selectedEffort"] = payload.get("effort") or run["selectedEffort"]
    run["status"] = "complete"
    return run
