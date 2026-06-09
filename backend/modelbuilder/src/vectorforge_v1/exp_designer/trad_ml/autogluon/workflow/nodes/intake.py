from __future__ import annotations

from langgraph.types import interrupt

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


REQUIRED_FIELDS = {
    "dataset_path": "Please upload a cleaned CSV dataset.",
    "target_column": "Which column should AutoGluon predict?",
    "problem_statement": "What problem should the experiments solve?",
    "business_kpi": "What business KPI should the experiments optimize for?",
}


def clarify_user_request(state: RunState) -> dict:
    run_id = state["run_id"]
    user_request = dict(state.get("user_request") or {})
    missing_fields = _missing_fields(user_request)
    if missing_fields:
        payload = {
            "type": "clarification_required",
            "missing_fields": missing_fields,
            "questions": [REQUIRED_FIELDS[field] for field in missing_fields],
        }
        ArtifactStore().write_status(run_id, "awaiting_clarification", {"interrupt": payload})
        resume_payload = interrupt(payload)
        if isinstance(resume_payload, dict):
            user_request.update({key: value for key, value in resume_payload.items() if value is not None})
        missing_fields = _missing_fields(user_request)

    clarification = {
        "is_complete": not missing_fields,
        "missing_fields": missing_fields,
        "questions": [REQUIRED_FIELDS[field] for field in missing_fields],
    }
    return {
        "status": "created" if not missing_fields else "awaiting_clarification",
        "user_request": user_request,
        "clarification": clarification,
        "events": [{"node": "clarify_user_request", "status": "completed", "message": "Input completeness checked."}],
    }


def create_run_artifacts(state: RunState) -> dict:
    run_id = state["run_id"]
    user_request = dict(state["user_request"])
    dataset_path = ArtifactStore().materialize_input(run_id, user_request["dataset_path"], user_request)
    user_request["dataset_path"] = str(dataset_path)
    return {
        "status": "created",
        "user_request": user_request,
        "events": [{"node": "create_run_artifacts", "status": "completed", "message": "Run artifacts created."}],
    }


def _missing_fields(user_request: dict) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not user_request.get(field)]
