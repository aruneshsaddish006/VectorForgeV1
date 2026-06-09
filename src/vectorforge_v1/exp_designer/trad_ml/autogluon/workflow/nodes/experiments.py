from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.autogluon_runner import ExperimentRunner
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import ExperimentTaskState


def run_experiment(state: ExperimentTaskState) -> dict:
    user_request = state["user_request"]
    planner_decision = state["planner_decision"]
    result = ExperimentRunner().run(
        run_id=state["run_id"],
        round_number=state["round"],
        experiment=state["experiment"],
        dataset_path=user_request["dataset_path"],
        target_column=user_request["target_column"] or "",
        task_type=planner_decision["task_type"],
        primary_metric=planner_decision["selected_primary_metric"],
        experiments_per_round=state.get("experiments_per_round", 1),
    )
    return {
        "experiment_results": [result],
        "events": [{"node": "run_experiment", "status": result["status"], "message": result["experiment_id"]}],
    }
