from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.profiler import CSVProfiler
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def profile_dataset(state: RunState) -> dict:
    run_id = state["run_id"]
    ArtifactStore().write_status(run_id, "profiling")
    user_request = state["user_request"]
    try:
        path = CSVProfiler().profile(run_id, user_request["dataset_path"], user_request["target_column"] or "")
        return {
            "status": "profiling",
            "profile_success": True,
            "dataset_profile_path": str(path),
            "events": [{"node": "profile_dataset", "status": "completed", "message": "Dataset profiled."}],
        }
    except Exception as exc:
        return {
            "status": "failed",
            "profile_success": False,
            "errors": [{"node": "profile_dataset", "message": str(exc)}],
        }
