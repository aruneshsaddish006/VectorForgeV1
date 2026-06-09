from __future__ import annotations

from langgraph.types import interrupt

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def await_user_confirmation(state: RunState) -> dict:
    payload = {
        "type": "planner_confirmation_required",
        "planner_decision": state.get("planner_decision"),
        "action": "confirm_to_start_experiments",
    }
    ArtifactStore().write_status(state["run_id"], "awaiting_confirmation", {"interrupt": payload})
    resume_payload = interrupt(payload)
    confirmed = bool(resume_payload.get("confirmed")) if isinstance(resume_payload, dict) else bool(resume_payload)
    status = "queued" if confirmed else "failed"
    ArtifactStore().write_status(state["run_id"], status)
    update = {
        "status": status,
        "confirmation_confirmed": confirmed,
        "events": [{"node": "await_user_confirmation", "status": "completed", "message": "Confirmation received."}],
    }
    if not confirmed:
        update["errors"] = [{"node": "await_user_confirmation", "message": "User rejected planner decision."}]
    return update
