from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.confirmation import await_user_confirmation
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.experiments import run_experiment
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.failure import mark_failed
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.finalization import select_final_winner, write_final_recommendation
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.intake import clarify_user_request, create_run_artifacts
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.planning import (
    plan_initial_metric_decision,
    plan_round_experiments,
    validate_initial_decision,
    validate_round_plan,
)
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.profiling import profile_dataset
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.nodes.rounds import (
    collect_round_results,
    dispatch_experiments,
    initialize_round,
    select_round_winner,
    should_continue_rounds,
    summarize_round,
)
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.routes import (
    fan_out_experiments,
    route_after_clarification,
    route_after_confirmation,
    route_after_initial_validation,
    route_after_profile,
    route_after_result_collection,
    route_after_round_decision,
    route_after_round_plan_validation,
)
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def build_autoresearch_graph():
    builder = StateGraph(RunState)

    builder.add_node("clarify_user_request", clarify_user_request)
    builder.add_node("create_run_artifacts", create_run_artifacts)
    builder.add_node("profile_dataset", profile_dataset)
    builder.add_node("plan_initial_metric_decision", plan_initial_metric_decision)
    builder.add_node("validate_initial_decision", validate_initial_decision)
    builder.add_node("await_user_confirmation", await_user_confirmation)
    builder.add_node("initialize_round", initialize_round)
    builder.add_node("plan_round_experiments", plan_round_experiments)
    builder.add_node("validate_round_plan", validate_round_plan)
    builder.add_node("dispatch_experiments", dispatch_experiments)
    builder.add_node("run_experiment", run_experiment)
    builder.add_node("collect_round_results", collect_round_results)
    builder.add_node("select_round_winner", select_round_winner)
    builder.add_node("summarize_round", summarize_round)
    builder.add_node("should_continue_rounds", should_continue_rounds)
    builder.add_node("select_final_winner", select_final_winner)
    builder.add_node("write_final_recommendation", write_final_recommendation)
    builder.add_node("mark_failed", mark_failed)

    builder.add_edge(START, "clarify_user_request")
    builder.add_conditional_edges("clarify_user_request", route_after_clarification)
    builder.add_edge("create_run_artifacts", "profile_dataset")
    builder.add_conditional_edges("profile_dataset", route_after_profile)
    builder.add_edge("plan_initial_metric_decision", "validate_initial_decision")
    builder.add_conditional_edges("validate_initial_decision", route_after_initial_validation)
    builder.add_conditional_edges("await_user_confirmation", route_after_confirmation)
    builder.add_edge("initialize_round", "plan_round_experiments")
    builder.add_edge("plan_round_experiments", "validate_round_plan")
    builder.add_conditional_edges("validate_round_plan", route_after_round_plan_validation)
    builder.add_conditional_edges("dispatch_experiments", fan_out_experiments)
    builder.add_edge("run_experiment", "collect_round_results")
    builder.add_conditional_edges("collect_round_results", route_after_result_collection)
    builder.add_edge("select_round_winner", "summarize_round")
    builder.add_edge("summarize_round", "should_continue_rounds")
    builder.add_conditional_edges("should_continue_rounds", route_after_round_decision)
    builder.add_edge("select_final_winner", "write_final_recommendation")
    builder.add_edge("write_final_recommendation", END)
    builder.add_edge("mark_failed", END)

    return builder.compile(checkpointer=InMemorySaver())


autoresearch_graph = build_autoresearch_graph()
