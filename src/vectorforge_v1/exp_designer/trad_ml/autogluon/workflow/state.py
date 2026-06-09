from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict


class UserRequest(TypedDict, total=False):
    dataset_path: str
    target_column: str | None
    problem_statement: str | None
    business_kpi: str | None


class ClarificationState(TypedDict):
    is_complete: bool
    missing_fields: list[str]
    questions: list[str]


class PlannerDecision(TypedDict):
    task_type: Literal["binary_classification", "multiclass_classification", "regression"]
    metric_candidates: list[dict]
    selected_primary_metric: str
    secondary_metrics: list[str]
    profile: str
    reasoning: str


class RoundPlan(TypedDict):
    round: int
    round_goal: str
    experiments: list[dict]


class ExperimentResult(TypedDict):
    round: int
    experiment_id: str
    status: Literal["completed", "failed"]
    primary_metric: str
    primary_metric_value: float | None
    metrics_path: str
    config_path: str
    model_path: str | None
    error_summary: str | None
    secondary_metrics: dict[str, float | int | None]
    holdout_metrics_path: str | None
    model_manifest_path: str | None


class WorkflowError(TypedDict):
    node: str
    message: str


class WorkflowEvent(TypedDict):
    node: str
    status: str
    message: str


class RunState(TypedDict, total=False):
    run_id: str
    session_id: str
    status: str
    current_round: int
    max_rounds: int
    experiments_per_round: int

    user_request: UserRequest
    clarification: ClarificationState | None

    dataset_profile_path: str | None
    metric_decision_path: str | None
    planner_decision: PlannerDecision | None

    round_plan_path: str | None
    current_round_plan: RoundPlan | None
    experiment_results: Annotated[list[ExperimentResult], operator.add]

    leaderboard_path: str | None
    current_best_experiment_id: str | None
    final_recommendation_path: str | None

    errors: Annotated[list[WorkflowError], operator.add]
    events: Annotated[list[WorkflowEvent], operator.add]

    initial_decision_valid: bool
    profile_success: bool
    round_plan_valid: bool
    confirmation_confirmed: bool
    round_success: bool
    final_winner: ExperimentResult | None


class ExperimentTaskState(TypedDict):
    run_id: str
    session_id: str
    user_request: UserRequest
    planner_decision: PlannerDecision
    experiment: dict
    round: int
    experiments_per_round: int
