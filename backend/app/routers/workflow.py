from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query

from app.schemas.workflow import BillingApprovalRequest, DatasetConfirmRequest, ExaRunRequest, ProblemIntakeRequest
from app.services.demo_data import DATA_SOURCE_PATHS, DEMO_WORKSPACE, make_exa_run
from app.services.experiment_results_stream import experiment_results_stream


router = APIRouter(prefix="/api", tags=["workflow"])


@router.get("/demo-workspace")
def demo_workspace() -> dict[str, Any]:
    return DEMO_WORKSPACE


@router.post("/problem-intake")
def problem_intake(payload: ProblemIntakeRequest) -> dict[str, Any]:
    return {
        "intent": "classification",
        "clarifyingQuestions": [
            "Which customer segment should the model prioritize?",
            "How far before renewal should the churn signal fire?",
            "Which intervention KPI should define success?",
        ],
        "next": "strategy",
        "received": payload.model_dump(),
    }


@router.get("/strategy")
def strategy() -> dict[str, Any]:
    return DEMO_WORKSPACE["strategy"]


@router.get("/data-sources")
def data_sources() -> list[dict[str, Any]]:
    return DATA_SOURCE_PATHS


@router.post("/exa/runs", status_code=201)
def create_exa_run(payload: ExaRunRequest) -> dict[str, Any]:
    return make_exa_run(payload.model_dump())


@router.get("/exa/runs/{run_id}")
def exa_run(run_id: str) -> dict[str, Any]:
    return {**DEMO_WORKSPACE["exaRun"], "id": run_id}


@router.get("/datasets/{dataset_id}/schema")
def dataset_schema(dataset_id: str) -> dict[str, Any]:
    return {**DEMO_WORKSPACE["dataset"], "id": dataset_id}


@router.post("/datasets/{dataset_id}/confirm")
def confirm_dataset(dataset_id: str, payload: DatasetConfirmRequest) -> dict[str, Any]:
    return {
        "datasetId": dataset_id,
        "targetColumn": payload.target_column,
        "applyQualityFixes": payload.apply_quality_fixes,
        "status": "confirmed",
        "next": "training",
    }


@router.post("/training/runs", status_code=201)
def create_training_run() -> dict[str, Any]:
    return DEMO_WORKSPACE["training"]


@router.get("/training/runs/{run_id}")
def training_run(run_id: str) -> dict[str, Any]:
    return {**DEMO_WORKSPACE["training"], "id": run_id}


@router.get("/rag/runs/{run_id}")
def rag_run(run_id: str) -> dict[str, Any]:
    return {**DEMO_WORKSPACE["rag"], "id": run_id}


@router.post("/deployments", status_code=201)
def create_deployment() -> dict[str, Any]:
    return {
        "id": f"dep_{uuid4().hex[:8]}",
        "status": "deployed",
        "modelApiUrl": "https://api.forgeai.demo/acme/churn/v1",
        "ragApiUrl": "https://api.forgeai.demo/acme/rag/v1",
    }


@router.post("/billing/approve")
def approve_billing(payload: BillingApprovalRequest) -> dict[str, Any]:
    return {
        "approvalId": payload.approval_id,
        "approvedBy": payload.approved_by,
        "status": "approved",
        "amount": "$1.94",
    }


@router.get("/activity")
def activity() -> list[dict[str, Any]]:
    return DEMO_WORKSPACE["activity"]


@router.get("/sessions/{session_id}/experiment-results")
def experiment_results(
    session_id: str,
    after: str = Query("0-0"),
    count: int = Query(100, ge=1, le=500),
    block_ms: int = Query(0, ge=0, le=30000),
) -> dict[str, Any]:
    return experiment_results_stream.poll(
        session_id=session_id,
        after=after,
        count=count,
        block_ms=block_ms,
    )
