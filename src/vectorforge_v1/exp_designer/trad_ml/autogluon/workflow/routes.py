from __future__ import annotations

from langgraph.types import Send

from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def route_after_clarification(state: RunState) -> str:
    clarification = state.get("clarification") or {}
    return "create_run_artifacts" if clarification.get("is_complete") else "mark_failed"


def route_after_initial_validation(state: RunState) -> str:
    return "await_user_confirmation" if state.get("initial_decision_valid") else "mark_failed"


def route_after_profile(state: RunState) -> str:
    return "plan_initial_metric_decision" if state.get("profile_success") else "mark_failed"


def route_after_confirmation(state: RunState) -> str:
    return "initialize_round" if state.get("confirmation_confirmed") else "mark_failed"


def route_after_round_plan_validation(state: RunState) -> str:
    return "dispatch_experiments" if state.get("round_plan_valid") else "mark_failed"


def fan_out_experiments(state: RunState) -> list[Send]:
    plan = state.get("current_round_plan") or {}
    planner_decision = state.get("planner_decision")
    if not planner_decision:
        return []
    return [
        Send(
            "run_experiment",
            {
                "run_id": state["run_id"],
                "user_request": state["user_request"],
                "planner_decision": planner_decision,
                "experiment": experiment,
                "round": plan["round"],
                "experiments_per_round": state.get("experiments_per_round", 1),
            },
        )
        for experiment in plan.get("experiments", [])
    ]


def route_after_result_collection(state: RunState) -> str:
    return "select_round_winner" if state.get("round_success") else "mark_failed"


def route_after_round_decision(state: RunState) -> str:
    if state.get("current_round", 0) < state.get("max_rounds", 3):
        return "initialize_round"
    return "select_final_winner"
