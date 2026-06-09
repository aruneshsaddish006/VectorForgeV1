from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from langgraph.types import Command

from vectorforge_v1.artifact_forge.artifact_resolver import ensure_artifact_zip_for_run, find_artifact_zip_in_run_dir
from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings
from vectorforge_v1.exp_designer.trad_ml.autogluon.schemas.requests import ClarificationPayload, ConfirmationPayload
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ACTIVE_STATUSES, ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.graph import autoresearch_graph

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("")
async def create_run(
    dataset: UploadFile | None = File(default=None),
    target_column: str | None = Form(default=None),
    problem_statement: str | None = Form(default=None),
    business_kpi: str | None = Form(default=None),
    max_rounds: int | None = Form(default=None),
    experiments_per_round: int | None = Form(default=None),
) -> dict[str, Any]:
    store = ArtifactStore()
    if store.has_active_run():
        raise HTTPException(status_code=409, detail={"message": "Another run is active", "active_runs": store.list_active_runs()})

    run_id = _new_run_id()
    store.create_pending_run(run_id)
    staged_dataset = await store.stage_upload(run_id, dataset) if dataset else None
    initial_state = _initial_state(
        run_id=run_id,
        dataset_path=str(staged_dataset) if staged_dataset else "",
        target_column=target_column,
        problem_statement=problem_statement,
        business_kpi=business_kpi,
        max_rounds=max_rounds,
        experiments_per_round=experiments_per_round,
    )
    result = autoresearch_graph.invoke(initial_state, _graph_config(run_id), version="v2")
    return _response_from_graph_result(run_id, result)


@router.get("")
def list_runs() -> dict[str, Any]:
    runs = ArtifactStore().list_runs()
    return {"runs": runs, "active_runs": [run for run in runs if run.get("is_active")]}


@router.post("/active/mark-failed")
def mark_active_runs_failed() -> dict[str, Any]:
    failed_run_ids = ArtifactStore().mark_active_runs_failed("Manually marked failed through API.")
    return {"status": "ok", "failed_run_ids": failed_run_ids}


@router.post("/{run_id}/clarify")
def clarify_run(run_id: str, payload: ClarificationPayload) -> dict[str, Any]:
    _require_status(run_id, {"awaiting_clarification"})
    result = autoresearch_graph.invoke(
        Command(resume=payload.model_dump(exclude_none=True)),
        _graph_config(run_id),
        version="v2",
    )
    return _response_from_graph_result(run_id, result)


@router.post("/{run_id}/confirm")
def confirm_run(run_id: str, payload: ConfirmationPayload, background_tasks: BackgroundTasks) -> dict[str, Any]:
    _require_status(run_id, {"awaiting_confirmation"})
    store = ArtifactStore()
    if payload.confirmed:
        store.write_status(run_id, "queued")
        background_tasks.add_task(_resume_confirmation, run_id, payload.confirmed)
        return {"run_id": run_id, "status": "queued"}

    result = autoresearch_graph.invoke(Command(resume={"confirmed": False}), _graph_config(run_id), version="v2")
    return _response_from_graph_result(run_id, result)


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    store = ArtifactStore()
    try:
        status = store.read_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run_dir = store.run_dir(run_id)
    metric_decision_path = run_dir / "planning" / "metric_decision.json"
    return {
        "run_id": run_id,
        "status": status.get("status"),
        "current_round": status.get("current_round"),
        "planner_decision": store.read_json(metric_decision_path) if metric_decision_path.exists() else None,
        "rounds": _round_summaries(run_dir),
        "final_recommendation_path": status.get("final_recommendation_path"),
        "error": status.get("error"),
    }


@router.get("/{run_id}/leaderboard")
def get_leaderboard(run_id: str):
    path = ArtifactStore().run_dir(run_id) / "reports" / "leaderboard.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Leaderboard is not available yet")
    return FileResponse(path, media_type="text/csv", filename="leaderboard.csv")


@router.get("/{run_id}/research-log")
def get_research_log(run_id: str):
    path = ArtifactStore().run_dir(run_id) / "reports" / "research_log.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Research log is not available yet")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/{run_id}/final-recommendation")
def get_final_recommendation(run_id: str) -> dict[str, Any]:
    path = ArtifactStore().run_dir(run_id) / "reports" / "final_recommendation.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Final recommendation is not available yet")
    return ArtifactStore().read_json(path)


@router.get("/{run_id}/artifacts/final-model")
def get_final_model(run_id: str) -> dict[str, Any]:
    recommendation_path = ArtifactStore().run_dir(run_id) / "reports" / "final_recommendation.json"
    if not recommendation_path.exists():
        raise HTTPException(status_code=404, detail="Final model is not available yet")
    recommendation = ArtifactStore().read_json(recommendation_path)
    return {"run_id": run_id, "model_path": recommendation.get("winning_model_path")}


@router.post("/{run_id}/generate-artifact")
def generate_artifact_endpoint(run_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    _require_status(run_id, {"completed"})
    store = ArtifactStore()
    recommendation_path = store.run_dir(run_id) / "reports" / "final_recommendation.json"
    if not recommendation_path.exists():
        raise HTTPException(status_code=404, detail="final_recommendation.json not found — run may not have completed correctly")
    recommendation = store.read_json(recommendation_path)
    winner = {
        "experiment_id": recommendation.get("best_experiment_id"),
        "primary_metric": recommendation.get("primary_metric"),
        "primary_metric_value": recommendation.get("best_score"),
        "secondary_metrics": recommendation.get("secondary_metrics", {}),
        "model_path": recommendation.get("winning_model_path"),
        "model_manifest_path": recommendation.get("winning_model_manifest_path"),
        "holdout_metrics_path": recommendation.get("holdout_metrics_path"),
    }
    run_dir = store.run_dir(run_id)
    background_tasks.add_task(_run_generate_artifact, run_id, winner, run_dir)
    return {"run_id": run_id, "status": "artifact_generation_queued"}


@router.get("/{run_id}/artifacts/package")
def get_artifact_package(run_id: str):
    store = ArtifactStore()
    try:
        store.read_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run_dir = store.run_dir(run_id)
    zip_path = find_artifact_zip_in_run_dir(run_dir)
    if not zip_path:
        try:
            zip_path = ensure_artifact_zip_for_run(
                run_id=run_id,
                run_dir=run_dir,
                engine_type="autogluon_tabular",
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Artifact generation failed: {exc}") from exc

    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


@router.post("/{run_id}/mark-failed")
def mark_run_failed(run_id: str) -> dict[str, Any]:
    try:
        ArtifactStore().mark_run_failed(run_id, "Manually marked failed through API.")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "failed"}


def _run_generate_artifact(run_id: str, winner: dict[str, Any], run_dir: Path) -> None:
    try:
        from vectorforge_v1.artifact_forge import generate_artifact
        generate_artifact("autogluon_tabular", run_id=run_id, winner=winner, run_dir=run_dir)
    except Exception as exc:
        ArtifactStore().write_status(run_id, "completed", {"artifact_status": "failed", "artifact_error": str(exc)})


def _resume_confirmation(run_id: str, confirmed: bool) -> None:
    try:
        autoresearch_graph.invoke(Command(resume={"confirmed": confirmed}), _graph_config(run_id), version="v2")
    except Exception as exc:
        ArtifactStore().write_status(run_id, "failed", {"error": str(exc)})


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{timestamp}_{uuid.uuid4().hex[:8]}"


def _initial_state(
    run_id: str,
    dataset_path: str,
    target_column: str | None,
    problem_statement: str | None,
    business_kpi: str | None,
    max_rounds: int | None = None,
    experiments_per_round: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    resolved_max_rounds = _positive_int(max_rounds, settings.max_rounds, "max_rounds")
    resolved_experiments_per_round = _positive_int(
        experiments_per_round,
        settings.experiments_per_round,
        "experiments_per_round",
    )
    return {
        "run_id": run_id,
        "status": "created",
        "current_round": 0,
        "max_rounds": resolved_max_rounds,
        "experiments_per_round": resolved_experiments_per_round,
        "user_request": {
            "dataset_path": dataset_path,
            "target_column": target_column,
            "problem_statement": problem_statement,
            "business_kpi": business_kpi,
        },
        "clarification": None,
        "dataset_profile_path": None,
        "metric_decision_path": None,
        "planner_decision": None,
        "round_plan_path": None,
        "current_round_plan": None,
        "experiment_results": [],
        "leaderboard_path": None,
        "current_best_experiment_id": None,
        "final_recommendation_path": None,
        "errors": [],
        "events": [],
        "profile_success": False,
        "initial_decision_valid": False,
        "round_plan_valid": False,
        "confirmation_confirmed": False,
        "round_success": False,
        "final_winner": None,
    }


def _graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _response_from_graph_result(run_id: str, result: Any) -> dict[str, Any]:
    store = ArtifactStore()
    state = getattr(result, "value", result) or {}
    interrupts = [interrupt.value for interrupt in getattr(result, "interrupts", ()) or ()]
    status = store.read_status(run_id).get("status")
    response = {
        "run_id": run_id,
        "status": status,
        "interrupt": interrupts[0] if interrupts else None,
        "planner_decision": state.get("planner_decision"),
        "state": _summarize_state(state),
    }
    return response


def _summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_round": state.get("current_round"),
        "dataset_profile_path": state.get("dataset_profile_path"),
        "metric_decision_path": state.get("metric_decision_path"),
        "round_plan_path": state.get("round_plan_path"),
        "leaderboard_path": state.get("leaderboard_path"),
        "final_recommendation_path": state.get("final_recommendation_path"),
        "current_best_experiment_id": state.get("current_best_experiment_id"),
        "max_rounds": state.get("max_rounds"),
        "experiments_per_round": state.get("experiments_per_round"),
        "errors": state.get("errors", []),
    }


def _positive_int(value: int | None, default: int, field_name: str) -> int:
    resolved = default if value is None else value
    if resolved < 1:
        raise HTTPException(status_code=422, detail=f"{field_name} must be at least 1")
    return resolved


def _require_status(run_id: str, allowed_statuses: set[str]) -> None:
    try:
        status = ArtifactStore().read_status(run_id).get("status")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status not in allowed_statuses:
        raise HTTPException(status_code=409, detail=f"Run is {status}; expected one of {sorted(allowed_statuses)}")


def _round_summaries(run_dir: Path) -> list[dict[str, Any]]:
    experiments_dir = run_dir / "experiments"
    rounds: list[dict[str, Any]] = []
    if not experiments_dir.exists():
        return rounds
    store = ArtifactStore()
    for round_dir in sorted(experiments_dir.glob("round_*")):
        experiments = []
        for experiment_dir in sorted(round_dir.iterdir()):
            status_path = experiment_dir / "status.json"
            metrics_path = experiment_dir / "metrics.json"
            status = store.read_json(status_path) if status_path.exists() else {}
            metrics = store.read_json(metrics_path) if metrics_path.exists() else {}
            experiments.append(
                {
                    "experiment_id": experiment_dir.name,
                    "status": status.get("status"),
                    "phase": status.get("phase"),
                    "elapsed_seconds": status.get("elapsed_seconds"),
                    "estimated_remaining_seconds": status.get("estimated_remaining_seconds"),
                    "fit_strategy": status.get("fit_strategy"),
                    "num_cpus": status.get("num_cpus"),
                    "num_bag_folds": status.get("num_bag_folds"),
                    "num_stack_levels": status.get("num_stack_levels"),
                    "progress_completed": status.get("progress_completed"),
                    "progress_total": status.get("progress_total"),
                    "progress_percent": status.get("progress_percent"),
                    "primary_metric_value": metrics.get("primary_metric_value"),
                }
            )
        rounds.append({"round": round_dir.name.removeprefix("round_"), "experiments": experiments})
    return rounds
