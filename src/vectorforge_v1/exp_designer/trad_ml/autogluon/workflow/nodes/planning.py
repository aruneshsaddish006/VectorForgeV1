from __future__ import annotations

from pathlib import Path

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.planner import get_planner
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


SUPPORTED_METRICS = {
    "binary_classification": {"f1", "recall", "precision", "roc_auc", "accuracy"},
    "multiclass_classification": {"accuracy", "f1_macro", "balanced_accuracy"},
    "regression": {"root_mean_squared_error", "mean_absolute_error", "r2"},
}

ALLOWED_INTENTS = {
    "fast_baseline",
    "quality_search",
    "balanced_ensemble",
    "deployable_simple",
    "imbalance_aware",
    "threshold_tuning",
    "regression_quality",
    "multiclass_quality",
}

ALLOWED_CONFIG_FIELDS = {
    "presets",
    "time_limit",
    "fit_weighted_ensemble",
    "calibrate_decision_threshold",
    "included_model_families",
    "infer_limit",
    "num_bag_folds",
    "num_stack_levels",
    "save_bag_folds",
}


def plan_initial_metric_decision(state: RunState) -> dict:
    run_id = state["run_id"]
    ArtifactStore().write_status(run_id, "planning")
    path = get_planner().plan_initial_metric_decision(run_id, state["user_request"], state["dataset_profile_path"] or "")
    decision = ArtifactStore().read_json(path)
    return {
        "status": "planning",
        "metric_decision_path": str(path),
        "planner_decision": decision,
        "events": [{"node": "plan_initial_metric_decision", "status": "completed", "message": "Planner decision created."}],
    }


def validate_initial_decision(state: RunState) -> dict:
    decision = state.get("planner_decision") or {}
    task_type = decision.get("task_type")
    metric = decision.get("selected_primary_metric")
    valid = bool(task_type in SUPPORTED_METRICS and metric in SUPPORTED_METRICS[task_type])
    update = {
        "initial_decision_valid": valid,
        "events": [{"node": "validate_initial_decision", "status": "completed", "message": "Decision validated."}],
    }
    if not valid:
        update["errors"] = [{"node": "validate_initial_decision", "message": "Unsupported task type or metric."}]
    return update


def plan_round_experiments(state: RunState) -> dict:
    run_id = state["run_id"]
    round_number = state["current_round"]
    path = get_planner().plan_round(
        run_id,
        round_number,
        state["planner_decision"] or {},
        state.get("experiments_per_round", 3),
        state.get("max_rounds", 3),
    )
    plan = ArtifactStore().read_json(Path(path))
    return {
        "round_plan_path": str(path),
        "current_round_plan": plan,
        "events": [{"node": "plan_round_experiments", "status": "completed", "message": f"Round {round_number} planned."}],
    }


def validate_round_plan(state: RunState) -> dict:
    plan = state.get("current_round_plan") or {}
    experiments = plan.get("experiments") or []
    valid = len(experiments) == state.get("experiments_per_round", 3)
    for experiment in experiments:
        config = experiment.get("config", {})
        valid = valid and experiment.get("intent") in ALLOWED_INTENTS
        valid = valid and set(config).issubset(ALLOWED_CONFIG_FIELDS)
        valid = valid and 1 <= int(config.get("time_limit", 300)) <= 900
    update = {
        "round_plan_valid": bool(valid),
        "events": [{"node": "validate_round_plan", "status": "completed", "message": "Round plan validated."}],
    }
    if not valid:
        update["errors"] = [{"node": "validate_round_plan", "message": "Round plan failed V1 validation."}]
    return update
