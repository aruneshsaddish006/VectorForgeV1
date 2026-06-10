from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_artifact_zip_in_run_dir(run_dir: Path) -> Path | None:
    status_path = run_dir / "status.json"
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            zip_path_str = status.get("artifact_zip_path")
            if zip_path_str:
                zip_path = Path(zip_path_str)
                if zip_path.exists():
                    return zip_path
        except Exception:
            pass

    artifact_dir = run_dir / "artifact"
    if artifact_dir.exists():
        zips = sorted(artifact_dir.glob("*.zip"))
        if zips:
            return zips[-1]
    return None


def ensure_artifact_zip_for_run(
    *,
    run_id: str,
    run_dir: Path,
    engine_type: str | None = None,
) -> Path:
    existing = find_artifact_zip_in_run_dir(run_dir)
    if existing:
        return existing

    recommendation_path = run_dir / "reports" / "final_recommendation.json"
    if not recommendation_path.exists():
        raise FileNotFoundError(f"final_recommendation.json not found for run '{run_id}'")

    recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
    resolved_engine_type = engine_type or _engine_type_from_recommendation(recommendation)
    winner = _winner_from_recommendation(recommendation, run_dir, resolved_engine_type)

    from vectorforge_v1.artifact_forge import generate_artifact

    zip_path = generate_artifact(
        resolved_engine_type,
        run_id=run_id,
        winner=winner,
        run_dir=run_dir,
    )
    if zip_path and Path(zip_path).exists():
        return Path(zip_path)

    error = _artifact_error(run_dir) or "artifact generation returned no zip"
    raise RuntimeError(error)


def _engine_type_from_recommendation(recommendation: dict[str, Any]) -> str:
    if recommendation.get("task_type") == "rag_optimization" or recommendation.get("winning_config_yaml_path"):
        return "autorag"
    return "autogluon_tabular"


def _winner_from_recommendation(
    recommendation: dict[str, Any],
    run_dir: Path,
    engine_type: str,
) -> dict[str, Any]:
    if engine_type == "autorag":
        return {
            "best_experiment_id": recommendation.get("best_experiment_id"),
            "primary_metric": recommendation.get("primary_metric"),
            "best_score": recommendation.get("best_score"),
            "secondary_metrics": recommendation.get("secondary_metrics", {}),
            "winning_config_yaml_path": _resolve_path(run_dir, recommendation.get("winning_config_yaml_path")),
            "corpus_path": _resolve_path(run_dir, recommendation.get("corpus_path")) or str(run_dir / "corpus.parquet"),
        }

    return {
        "experiment_id": recommendation.get("best_experiment_id"),
        "primary_metric": recommendation.get("primary_metric"),
        "primary_metric_value": recommendation.get("best_score"),
        "secondary_metrics": recommendation.get("secondary_metrics", {}),
        "model_path": _resolve_path(run_dir, recommendation.get("winning_model_path")),
        "model_manifest_path": _resolve_path(run_dir, recommendation.get("winning_model_manifest_path")),
        "holdout_metrics_path": _resolve_path(run_dir, recommendation.get("holdout_metrics_path")),
    }


def _rebase_to_runs(raw_path: Any) -> Path | None:
    """Strip any machine-specific prefix and rebase from the 'runs' folder anchor.

    Handles paths like /Users/arusaddi1/.../runs/orch_.../... by finding the
    'runs' segment and re-rooting under Path.cwd() / 'runs'.
    """
    if not raw_path:
        return None
    parts = Path(str(raw_path)).parts
    for i, part in enumerate(parts):
        if part == "runs":
            rebased = Path.cwd() / Path(*parts[i:])
            if rebased.exists():
                return rebased
    return None


def _resolve_path(run_dir: Path, raw_path: Any) -> str | None:
    if not raw_path:
        return None
    path = Path(str(raw_path)).expanduser()
    if path.exists():
        return str(path)

    rebased = _rebase_to_runs(raw_path)
    if rebased:
        return str(rebased)

    candidates = [
        run_dir / path,
        run_dir.parent / path,
        Path.cwd() / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(path)


def _artifact_error(run_dir: Path) -> str | None:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return None
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        return status.get("artifact_error")
    except Exception:
        return None


def deploy_artifact_for_folder(
    folder_id: str,
    *,
    allow_deploy: bool = False,
    force_rebuild: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Resolve a folder/run id to its artifact zip, build the Docker image, and
    (when allow_deploy and AWS creds are present in env_overrides) run deploy.sh.

    Returns DeployResult.to_dict(). Never raises — failures are reported in the
    returned dict's `status`/`error` fields.
    """
    from vectorforge_v1.artifact_forge.deploy.docker_runner import DockerDeployRunner
    from vectorforge_v1.artifact_forge.deploy.resolver import resolve_artifact_zip

    try:
        zip_path = resolve_artifact_zip(folder_id)
    except FileNotFoundError as exc:
        return {
            "status": "failed",
            "run_id": folder_id,
            "error": str(exc),
            "log_tail": [],
        }

    runner = DockerDeployRunner(
        run_id=folder_id,
        run_dir=zip_path.parent,
        allow_deploy=allow_deploy,
        force_rebuild=force_rebuild,
    )
    result = runner.run(zip_path=zip_path, env_overrides=env_overrides or {})
    return result.to_dict()
