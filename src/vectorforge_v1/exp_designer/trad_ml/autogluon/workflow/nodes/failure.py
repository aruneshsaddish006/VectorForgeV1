from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def mark_failed(state: RunState) -> dict:
    errors = state.get("errors", [])
    message = errors[-1]["message"] if errors else "Run failed."
    ArtifactStore().write_status(state["run_id"], "failed", {"error": message})
    return {
        "status": "failed",
        "events": [{"node": "mark_failed", "status": "completed", "message": message}],
    }
