"""
app.py — VectorForge V1 unified FastAPI application.

Mounts all sub-routers and adds top-level orchestrator endpoints:

  POST /orchestrate          — trigger a full multi-problem run (autogluon or autorag)
  GET  /orchestrate/{run_id} — poll orchestrator run status

Artifact download (by orchestrator run_id or designer run_id):
  GET  /runs/{run_id}/artifact/download — generate on demand and download the sealed artifact zip
  POST /runs/{run_id}/autorag/deploy    — load an in-process AutoRAG Runner by run_id
  POST /runs/{run_id}/autorag/invoke    — run a question through the loaded AutoRAG Runner

All existing routes from the autogluon designer and artifact-forge API are also
mounted unchanged:
  POST /runs                                          — autogluon designer run
  GET  /runs/{run_id}                                 — autogluon run status
  POST /runs/{run_id}/confirm                         — confirm autogluon run
  POST /artifact-forge/runs/{run_id}/trigger          — trigger artifact generation
  GET  /artifact-forge/runs/{run_id}/status           — artifact generation status
  GET  /artifact-forge/runs/{run_id}/download         — download artifact zip
  GET  /artifact-forge/runs/{run_id}/stream           — SSE stream of artifact nodes
  POST /artifact-forge/runs/{run_id}/invoke           — synchronous artifact invoke

Usage:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from vectorforge_v1.exp_designer.trad_ml.autogluon.api.config import router as config_router
from vectorforge_v1.exp_designer.trad_ml.autogluon.api.runs import router as runs_router
from vectorforge_v1.exp_designer.trad_ml.autogluon.api.workflow import router as workflow_router
from vectorforge_v1.artifact_forge.artifact_resolver import ensure_artifact_zip_for_run, find_artifact_zip_in_run_dir
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.artifact_forge.api.routes import router as artifact_forge_router


# ── Orchestrator run registry ────────────────────────────────────────────────
# In-process dict; fine for single-instance dev/demo use.
# Replace with a DB-backed store for multi-worker production.
_ORCH_RUNS: dict[str, dict[str, Any]] = {}
_ORCH_LOCK = threading.Lock()
_AUTORAG_DEPLOYS: dict[str, dict[str, Any]] = {}
_AUTORAG_DEPLOY_LOCK = threading.Lock()

# Resolved path to the runs base directory (matches ArtifactStore default)
_RUNS_DIR = Path("runs")


class SessionAutoRagDeployRequest(BaseModel):
    force_restart: bool = False


class AutoRagInvokeRequest(BaseModel):
    question: str | None = None
    query: str | None = None
    input: Any | None = None
    records: Any | None = None
    data: Any | None = None
    result_column: str = "generated_texts"


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    ArtifactStore().mark_active_runs_failed(
        "Server restarted; V1 in-memory graph checkpoints cannot resume active runs."
    )
    yield


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    application = FastAPI(
        title="VectorForge V1",
        description=(
            "Unified API for ML experiment orchestration, artifact generation, "
            "and deployment packaging. Supports autogluon (tabular ML) and "
            "autorag (RAG pipeline optimisation)."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── Existing sub-routers (autogluon designer + artifact-forge) ────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(config_router)
    application.include_router(workflow_router)
    application.include_router(runs_router)
    application.include_router(artifact_forge_router)

    return application


app = create_app()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_orch_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"orch_{ts}_{uuid.uuid4().hex[:8]}"


def _new_orchestrator_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}_{uuid.uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_files() -> None:
    for path in _candidate_env_paths():
        if path.exists():
            _load_env_file(path)
    _alias_redis_env()
    _alias_vectorforge_openai_env()


def _candidate_env_paths() -> list[Path]:
    app_root = Path(__file__).resolve().parent
    package_root = app_root / "src" / "vectorforge_v1"
    return [
        Path.cwd() / ".env",
        app_root / ".env",
        package_root / ".env",
        app_root.parent / "conversational" / ".env",
        app_root.parent / ".env",
        app_root.parent.parent / ".env",
    ]


def _load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] in {"'", '"'}:
            value = value.strip('"').strip("'")
        else:
            value = value.split(" #", 1)[0].strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _alias_vectorforge_openai_env() -> None:
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("VECTORFORGE_OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["VECTORFORGE_OPENAI_API_KEY"]
    if not os.environ.get("OPENAI_ADMIN_KEY") and os.environ.get("VECTORFORGE_OPENAI_ADMIN_KEY"):
        os.environ["OPENAI_ADMIN_KEY"] = os.environ["VECTORFORGE_OPENAI_ADMIN_KEY"]


def _alias_redis_env() -> None:
    redis_url = (
        os.environ.get("VECTORFORGE_REDIS_URL")
        or os.environ.get("VECTORFORGE_ELASTICACHE_REDIS_URL")
        or os.environ.get("ELASTICACHE_REDIS_URL")
        or os.environ.get("REDIS_URL")
    )
    if redis_url:
        os.environ.setdefault("VECTORFORGE_REDIS_URL", redis_url)
        os.environ.setdefault("REDIS_URL", redis_url)


def _redis_key(name: str) -> str:
    prefix = os.environ.get("VECTORFORGE_REDIS_CHANNEL_PREFIX", "vectorforge").strip(":")
    return f"{prefix}:{name.lstrip(':')}" if prefix else name.lstrip(":")


def _decode_stream_payload(fields: dict[str, Any]) -> dict[str, Any]:
    payload = fields.get("payload")
    if not payload:
        return fields
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


def _session_meta_key(session_id: str) -> str:
    return _redis_key(f"sessions:{session_id}:modelbuilder")


def _redis_client() -> Any | None:
    _load_env_files()
    redis_url = os.environ.get("VECTORFORGE_REDIS_URL")
    if not redis_url:
        return None
    import redis

    return redis.Redis.from_url(redis_url, decode_responses=True)


def _write_session_meta(session_id: str, updates: dict[str, Any]) -> None:
    try:
        client = _redis_client()
        if client is None:
            return
        key = _session_meta_key(session_id)
        current_raw = client.get(key)
        current = json.loads(current_raw) if current_raw else {}
        current.update(updates)
        current["updated_at"] = _utc_now()
        client.set(key, json.dumps(current, default=str))
    except Exception:
        # Session metadata is a convenience index; orchestration should not fail
        # if Redis is temporarily unavailable.
        return


def _read_session_meta(session_id: str) -> dict[str, Any]:
    try:
        client = _redis_client()
        if client is None:
            return {}
        raw = client.get(_session_meta_key(session_id))
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _resolve_autorag_trial_dir(resolved: dict[str, Any]) -> Path:
    designer_run_id = str(resolved["designer_run_id"])
    designer_run_dir = resolved.get("designer_run_dir")
    run_dir = Path(str(designer_run_dir)).expanduser() if designer_run_dir else _RUNS_DIR / designer_run_id
    if not run_dir.exists():
        run_dir = _RUNS_DIR / designer_run_id
    if not run_dir.exists():
        for candidate in _RUNS_DIR.rglob(designer_run_id):
            if candidate.is_dir():
                run_dir = candidate
                break
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"AutoRAG run directory not found for '{designer_run_id}'.")

    recommendation_path = run_dir / "reports" / "final_recommendation.json"
    if not recommendation_path.exists():
        raise HTTPException(status_code=404, detail=f"final_recommendation.json not found for '{designer_run_id}'.")

    recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
    project_path = recommendation.get("winning_model_path") or recommendation.get("optimization_project_dir")
    if not project_path:
        raise HTTPException(status_code=404, detail="AutoRAG final recommendation has no winning_model_path.")

    project_dir = Path(str(project_path)).expanduser()
    if not project_dir.exists():
        project_dir = run_dir / str(project_path)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"AutoRAG optimization project not found: {project_path}")

    trial_dir = project_dir / "0"
    if trial_dir.exists():
        return trial_dir

    trial_dirs = sorted([path for path in project_dir.iterdir() if path.is_dir() and path.name.isdigit()])
    if trial_dirs:
        return trial_dirs[-1]

    raise HTTPException(status_code=404, detail=f"No AutoRAG trial folder found under {project_dir}.")


def _orch_run_dir(orch_id: str) -> Path:
    return _RUNS_DIR / orch_id


def _find_artifact_zip(run_id: str) -> Path | None:
    """
    Locate an artifact zip for *run_id*.

    Searches in order:
    1. ArtifactStore().run_dir(run_id)/status.json  → artifact_zip_path
    2. ArtifactStore().run_dir(run_id)/artifact/*.zip
    3. Any orchestrator summary whose problem_results contain designer_run_id == run_id,
       then look inside that designer_run_dir/artifact/*.zip
    4. Direct scan of runs/<run_id>/artifact/*.zip (orchestrator-level run)
    """
    # 1. Direct designer run — status.json has artifact_zip_path
    designer_run_dir = _RUNS_DIR / run_id
    if designer_run_dir.exists():
        zip_path = find_artifact_zip_in_run_dir(designer_run_dir)
        if zip_path:
            return zip_path

    # 2. Orchestrator-level run — scan designer sub-dirs for matching run_id
    for summary_path in sorted(_RUNS_DIR.rglob("orchestrator_summary.json")):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for pr in summary.get("problem_results", []):
            if pr.get("designer_run_id") == run_id:
                d_dir = Path(pr.get("designer_run_dir", ""))
                if d_dir.exists():
                    zip_path = find_artifact_zip_in_run_dir(d_dir)
                    if zip_path:
                        return zip_path

    # 3. The run_id IS an orchestrator run_id — check its designers subdirectory
    orch_dir = _RUNS_DIR / run_id
    if orch_dir.exists():
        for zip_path in sorted(orch_dir.rglob("artifact/*.zip")):
            return zip_path

    return None


def _ensure_artifact_zip(run_id: str) -> Path:
    existing = _find_artifact_zip(run_id)
    if existing:
        return existing

    errors: list[str] = []
    for target in _artifact_download_targets(run_id):
        try:
            return ensure_artifact_zip_for_run(
                run_id=target["run_id"],
                run_dir=target["run_dir"],
                engine_type=target.get("engine_type"),
            )
        except Exception as exc:
            errors.append(f"{target['run_id']}: {exc}")

    if errors:
        raise HTTPException(
            status_code=500,
            detail="Artifact generation failed: " + "; ".join(errors),
        )

    raise HTTPException(
        status_code=404,
        detail=(
            f"No completed designer run with a final recommendation was found for '{run_id}'. "
            "Poll the orchestrator/run status first and retry after completion."
        ),
    )


def _artifact_download_targets(run_id: str) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[Path] = set()

    def add_target(target_run_id: str, run_dir: Path, engine_type: str | None = None) -> None:
        resolved = run_dir.resolve()
        if resolved in seen:
            return
        if not (run_dir / "reports" / "final_recommendation.json").exists():
            return
        seen.add(resolved)
        targets.append({"run_id": target_run_id, "run_dir": run_dir, "engine_type": engine_type})

    direct = _RUNS_DIR / run_id
    if direct.exists():
        add_target(run_id, direct)

    for status_path in sorted(_RUNS_DIR.rglob(f"{run_id}/status.json")):
        add_target(run_id, status_path.parent)

    for summary_path in sorted(_RUNS_DIR.rglob("orchestrator_summary.json")):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        is_requested_orchestrator = (
            summary.get("run_id") == run_id
            or (_RUNS_DIR / run_id).resolve() in summary_path.resolve().parents
        )

        for problem_result in summary.get("problem_results", []):
            designer_run_id = problem_result.get("designer_run_id")
            designer_run_dir = problem_result.get("designer_run_dir")
            if not designer_run_id or not designer_run_dir:
                continue
            if not is_requested_orchestrator and designer_run_id != run_id:
                continue
            add_target(
                str(designer_run_id),
                Path(designer_run_dir),
                _engine_type_from_problem_result(problem_result),
            )

    return targets


def _engine_type_from_problem_result(problem_result: dict[str, Any]) -> str | None:
    designer = str(problem_result.get("designer", "")).lower()
    if "autorag" in designer:
        return "autorag"
    if "autogluon" in designer:
        return "autogluon_tabular"
    return None


def _autorag_problem_result(summary: dict[str, Any]) -> dict[str, Any] | None:
    for problem_result in summary.get("problem_results", []):
        designer = str(problem_result.get("designer", "")).lower()
        designer_run_id = str(problem_result.get("designer_run_id") or "")
        if "autorag" in designer or "autorag" in designer_run_id:
            return problem_result
    return None


def _summary_from_orch_id(orch_id: str) -> dict[str, Any] | None:
    with _ORCH_LOCK:
        run = _ORCH_RUNS.get(orch_id)
    if run and isinstance(run.get("result"), dict):
        return run["result"]

    summary_paths = [
        _RUNS_DIR / orch_id / "reports" / "orchestrator_summary.json",
        *_RUNS_DIR.glob(f"{orch_id}/run_*/reports/orchestrator_summary.json"),
    ]
    for summary_path in summary_paths:
        if not summary_path.exists():
            continue
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _orchestrator_run_for_session(session_id: str) -> dict[str, Any] | None:
    meta = _read_session_meta(session_id)
    candidate_orch_ids: list[str] = []
    if meta.get("orch_id"):
        candidate_orch_ids.append(str(meta["orch_id"]))

    with _ORCH_LOCK:
        matching_runs = [
            dict(run)
            for run in _ORCH_RUNS.values()
            if run.get("session_id") == session_id
        ]
    if matching_runs:
        return max(matching_runs, key=lambda run: str(run.get("started_at") or ""))

    for orch_id in dict.fromkeys(candidate_orch_ids):
        with _ORCH_LOCK:
            run = _ORCH_RUNS.get(orch_id)
        if run:
            return dict(run)
        summary = _summary_from_orch_id(orch_id)
        if summary:
            return {"orch_id": orch_id, "source": "session_meta", **summary}

    for summary_path in sorted(_RUNS_DIR.rglob("orchestrator_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summary.get("session_id") != session_id:
            continue
        orch_id = summary_path.parents[1].name if len(summary_path.parents) > 1 else session_id
        return {"orch_id": orch_id, "source": "session_disk_scan", **summary}

    if meta:
        return {
            "orch_id": meta.get("orch_id"),
            "session_id": session_id,
            "status": meta.get("status", "unknown"),
            "source": "session_meta",
            **meta,
        }

    return None


def _resolve_autorag_run_for_session(session_id: str) -> dict[str, Any]:
    try:
        resolved_by_run_id = _resolve_autorag_run_for_run_id(session_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    else:
        resolved_by_run_id["requested_session_id"] = session_id
        return resolved_by_run_id

    meta = _read_session_meta(session_id)
    if meta.get("autorag_designer_run_id"):
        return {
            "session_id": session_id,
            "orch_id": meta.get("orch_id"),
            "orchestrator_run_id": meta.get("run_id"),
            "designer_run_id": meta["autorag_designer_run_id"],
            "designer_run_dir": meta.get("autorag_designer_run_dir"),
            "source": "redis",
        }

    candidate_orch_ids = []
    if meta.get("orch_id"):
        candidate_orch_ids.append(str(meta["orch_id"]))
    with _ORCH_LOCK:
        for orch_id, run in _ORCH_RUNS.items():
            if run.get("session_id") == session_id:
                candidate_orch_ids.append(orch_id)

    for orch_id in dict.fromkeys(candidate_orch_ids):
        summary = _summary_from_orch_id(orch_id)
        if not summary:
            continue
        problem_result = _autorag_problem_result(summary)
        if problem_result and problem_result.get("designer_run_id"):
            return {
                "session_id": session_id,
                "orch_id": orch_id,
                "orchestrator_run_id": summary.get("run_id"),
                "designer_run_id": problem_result["designer_run_id"],
                "designer_run_dir": problem_result.get("designer_run_dir"),
                "source": "orchestrator_summary",
            }

    for summary_path in sorted(_RUNS_DIR.rglob("orchestrator_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summary.get("session_id") != session_id:
            continue
        problem_result = _autorag_problem_result(summary)
        if problem_result and problem_result.get("designer_run_id"):
            return {
                "session_id": session_id,
                "orch_id": summary_path.parents[1].name if len(summary_path.parents) > 1 else None,
                "orchestrator_run_id": summary.get("run_id"),
                "designer_run_id": problem_result["designer_run_id"],
                "designer_run_dir": problem_result.get("designer_run_dir"),
                "source": "disk_scan",
            }

    raise HTTPException(status_code=404, detail=f"No completed AutoRAG designer run found for session '{session_id}'.")


def _resolve_autorag_run_for_run_id(run_id: str) -> dict[str, Any]:
    direct = _RUNS_DIR / run_id
    if (direct / "reports" / "final_recommendation.json").exists():
        return {
            "run_id": run_id,
            "designer_run_id": run_id,
            "designer_run_dir": str(direct),
            "source": "direct_run_dir",
        }

    for status_path in sorted(_RUNS_DIR.rglob(f"{run_id}/status.json")):
        run_dir = status_path.parent
        if (run_dir / "reports" / "final_recommendation.json").exists():
            return {
                "run_id": run_id,
                "designer_run_id": run_id,
                "designer_run_dir": str(run_dir),
                "source": "status_path",
            }

    summary_paths = sorted(
        _RUNS_DIR.rglob("orchestrator_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for summary_path in summary_paths:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        is_requested_orchestrator = (
            summary.get("run_id") == run_id
            or summary.get("session_id") == run_id
            or any(parent.name == run_id for parent in summary_path.parents)
        )
        problem_result = None
        if is_requested_orchestrator:
            problem_result = _autorag_problem_result(summary)
        else:
            for candidate in summary.get("problem_results", []):
                if candidate.get("designer_run_id") == run_id:
                    problem_result = candidate
                    break

        if problem_result and problem_result.get("designer_run_id"):
            return {
                "run_id": run_id,
                "session_id": summary.get("session_id"),
                "orchestrator_run_id": summary.get("run_id"),
                "designer_run_id": problem_result["designer_run_id"],
                "designer_run_dir": problem_result.get("designer_run_dir"),
                "source": "orchestrator_summary",
            }

    for status_path in sorted(_RUNS_DIR.rglob("status.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status.get("run_id") != run_id:
            continue
        run_dir = status_path.parent
        if (run_dir / "reports" / "final_recommendation.json").exists():
            return {
                "run_id": run_id,
                "designer_run_id": run_id,
                "designer_run_dir": str(run_dir),
                "source": "status_scan",
            }

    raise HTTPException(status_code=404, detail=f"No completed AutoRAG designer run found for run_id '{run_id}'.")


def _deploy_autorag_runner(
    deployment_id: str,
    resolved: dict[str, Any],
    body: SessionAutoRagDeployRequest,
    *,
    write_session_meta: bool,
) -> dict[str, Any]:
    _load_env_files()

    from vectorforge_v1.exp_designer.gen_ai.autorag.agentic_autorag import patch_openai_clients_for_local_ssl

    patch_openai_clients_for_local_ssl()

    from autorag.deploy import Runner

    designer_run_id = str(resolved["designer_run_id"])
    trial_dir = _resolve_autorag_trial_dir(resolved)

    with _AUTORAG_DEPLOY_LOCK:
        existing = _AUTORAG_DEPLOYS.get(deployment_id)
        if existing and existing.get("runner") is not None:
            if not body.force_restart:
                return {
                    key: value
                    for key, value in existing.items()
                    if key != "runner"
                }

        try:
            runner = Runner.from_trial_folder(str(trial_dir))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not initialize AutoRAG runner: {exc!s}") from exc

        deployment = {
            "deployment_id": deployment_id,
            "session_id": resolved.get("session_id"),
            "run_id": resolved.get("run_id"),
            "status": "ready",
            "deployment_mode": "autorag_runner_code",
            "trial_dir": str(trial_dir),
            "designer_run_id": designer_run_id,
            "designer_run_dir": resolved.get("designer_run_dir"),
            "orch_id": resolved.get("orch_id"),
            "orchestrator_run_id": resolved.get("orchestrator_run_id"),
            "started_at": _utc_now(),
            "source": resolved.get("source"),
            "runner": runner,
        }
        _AUTORAG_DEPLOYS[deployment_id] = deployment

    session_id = resolved.get("session_id")
    if write_session_meta and session_id:
        _write_session_meta(
            str(session_id),
            {
                "autorag_designer_run_id": designer_run_id,
                "autorag_designer_run_dir": resolved.get("designer_run_dir"),
                "autorag_runner_status": "ready",
                "autorag_runner_trial_dir": str(trial_dir),
            },
        )

    return {
        key: value
        for key, value in deployment.items()
        if key != "runner"
    }


def _autorag_deploy_status(deployment_id: str, *, not_found_detail: str) -> dict[str, Any]:
    with _AUTORAG_DEPLOY_LOCK:
        deployment = _AUTORAG_DEPLOYS.get(deployment_id)
        if not deployment:
            raise HTTPException(status_code=404, detail=not_found_detail)

        payload = {
            key: value
            for key, value in deployment.items()
            if key != "runner"
        }
        return payload


def _deployment_without_runner(deployment: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in deployment.items()
        if key != "runner"
    }


def _ensure_autorag_runner_for_identifier(identifier: str) -> dict[str, Any]:
    with _AUTORAG_DEPLOY_LOCK:
        deployment = _AUTORAG_DEPLOYS.get(identifier)
        if deployment and deployment.get("runner") is not None:
            return deployment

    resolution_errors: list[str] = []
    for resolver, write_session_meta in (
        (_resolve_autorag_run_for_run_id, False),
        (_resolve_autorag_run_for_session, True),
    ):
        try:
            resolved = resolver(identifier)
        except HTTPException as exc:
            if exc.status_code == 404:
                resolution_errors.append(str(exc.detail))
                continue
            raise
        resolved.setdefault("run_id", identifier)
        if write_session_meta:
            resolved.setdefault("session_id", identifier)
        _deploy_autorag_runner(
            identifier,
            resolved,
            SessionAutoRagDeployRequest(),
            write_session_meta=write_session_meta,
        )
        with _AUTORAG_DEPLOY_LOCK:
            deployment = _AUTORAG_DEPLOYS.get(identifier)
            if deployment and deployment.get("runner") is not None:
                return deployment

    raise HTTPException(
        status_code=404,
        detail=(
            f"No in-process AutoRAG runner found for '{identifier}', and no completed "
            f"AutoRAG designer run could be resolved. {'; '.join(resolution_errors)}"
        ),
    )


def _resolve_artifact_invoke_target(identifier: str) -> dict[str, Any]:
    targets = _artifact_download_targets(identifier)
    if targets:
        return targets[0]

    try:
        resolved = _resolve_autorag_run_for_session(identifier)
    except HTTPException:
        resolved = None
    if resolved:
        return {
            "run_id": str(resolved["designer_run_id"]),
            "run_dir": Path(str(resolved["designer_run_dir"])),
            "engine_type": "autorag",
        }

    raise HTTPException(status_code=404, detail=f"No completed designer run found for '{identifier}'.")


def _autogluon_input_payload(body: AutoRagInvokeRequest) -> Any | None:
    if body.input is not None:
        return body.input
    if body.records is not None:
        return body.records
    if body.data is not None:
        return body.data
    return None


def _safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            destination = (target_dir / member.filename).resolve()
            if target_dir.resolve() not in [destination, *destination.parents]:
                raise HTTPException(status_code=500, detail=f"Unsafe artifact zip member: {member.filename}")
        archive.extractall(target_dir)


def _find_extracted_infer_py(extract_dir: Path) -> Path:
    candidates = sorted(extract_dir.glob("*/infer.py")) + sorted(extract_dir.glob("infer.py"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=500, detail="infer.py not found in generated artifact zip.")


def _read_autogluon_artifact_io(identifier: str) -> dict[str, Any]:
    target = _resolve_artifact_invoke_target(identifier)
    if target.get("engine_type") != "autogluon_tabular":
        raise HTTPException(
            status_code=409,
            detail=f"Resolved run is {target.get('engine_type')}; this schema endpoint is for AutoGluon tabular artifacts.",
        )

    target_run_id = str(target["run_id"])
    target_run_dir = Path(target["run_dir"])
    zip_path = find_artifact_zip_in_run_dir(target_run_dir)
    if not zip_path:
        zip_path = ensure_artifact_zip_for_run(
            run_id=target_run_id,
            run_dir=target_run_dir,
            engine_type="autogluon_tabular",
        )

    with tempfile.TemporaryDirectory(prefix="vectorforge_autogluon_schema_") as tmp:
        extract_dir = Path(tmp) / "artifact"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract_zip(zip_path, extract_dir)
        infer_py = _find_extracted_infer_py(extract_dir)
        package_dir = infer_py.parent

        sample_path = package_dir / "sample_input.json"
        manifest_path = package_dir / "manifest.json"
        sample_input = json.loads(sample_path.read_text(encoding="utf-8")) if sample_path.exists() else []
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    sample_record = sample_input[0] if isinstance(sample_input, list) and sample_input else {}
    required_columns = list(sample_record.keys())
    input_schema = manifest.get("input_schema") or [
        {"name": key, "example": value, "type": type(value).__name__}
        for key, value in sample_record.items()
    ]
    return {
        "requested_id": identifier,
        "run_id": target_run_id,
        "engine_type": "autogluon_tabular",
        "run_dir": str(target_run_dir),
        "artifact_zip_path": str(zip_path),
        "required_columns": required_columns,
        "target_column_excluded": True,
        "input_schema": input_schema,
        "sample_record": sample_record,
        "sample_payload": {"input": [sample_record]} if sample_record else {"input": []},
    }


def _invoke_autogluon_artifact(identifier: str, target: dict[str, Any], body: AutoRagInvokeRequest) -> dict[str, Any]:
    target_run_id = str(target["run_id"])
    target_run_dir = Path(target["run_dir"])
    zip_path = find_artifact_zip_in_run_dir(target_run_dir)
    if not zip_path:
        try:
            zip_path = ensure_artifact_zip_for_run(
                run_id=target_run_id,
                run_dir=target_run_dir,
                engine_type=target.get("engine_type") or "autogluon_tabular",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"AutoGluon artifact is not ready for '{identifier}'. "
                    f"Trigger Artifact Forge and retry after artifact_status is completed. Cause: {exc!s}"
                ),
            ) from exc

    with tempfile.TemporaryDirectory(prefix="vectorforge_autogluon_infer_") as tmp:
        extract_dir = Path(tmp) / "artifact"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract_zip(zip_path, extract_dir)
        infer_py = _find_extracted_infer_py(extract_dir)
        package_dir = infer_py.parent

        input_payload = _autogluon_input_payload(body)
        if input_payload is None:
            input_path = package_dir / "sample_input.json"
            input_source = "sample_input.json"
            if not input_path.exists():
                raise HTTPException(
                    status_code=422,
                    detail="Provide AutoGluon tabular input via 'input', 'records', or 'data'.",
                )
        else:
            input_path = Path(tmp) / "input.json"
            input_path.write_text(json.dumps(input_payload, default=str), encoding="utf-8")
            input_source = "request"

        output_path = Path(tmp) / "predictions.json"
        proc = subprocess.run(
            [sys.executable, str(infer_py), "--input", str(input_path), "--output", str(output_path)],
            cwd=str(package_dir),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("VECTORFORGE_AUTOGLOON_INFER_TIMEOUT", "120")),
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "AutoGluon artifact inference failed.",
                    "stderr": proc.stderr[-4000:],
                    "stdout": proc.stdout[-4000:],
                },
            )

        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            result = {"stdout": proc.stdout}

    return {
        "deployment_id": identifier,
        "requested_id": identifier,
        "run_id": target_run_id,
        "engine_type": "autogluon_tabular",
        "run_dir": str(target_run_dir),
        "artifact_zip_path": str(zip_path),
        "input_source": input_source,
        "result": _json_safe(result),
        "invoked_at": _utc_now(),
    }


def _json_safe(value: Any) -> Any:
    try:
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            return value.to_dict(orient="records")
        if isinstance(value, pd.Series):
            return value.to_list()
    except Exception:
        pass

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    try:
        return jsonable_encoder(value)
    except Exception:
        return str(value)


def _exception_chain_message(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current)
        messages.append(f"{type(current).__name__}: {message}" if message else type(current).__name__)
        current = current.__cause__ or current.__context__
    return " <- ".join(messages)


def _autorag_invoke(deployment_id: str, body: AutoRagInvokeRequest) -> dict[str, Any]:
    target = _resolve_artifact_invoke_target(deployment_id)
    engine_type = target.get("engine_type")
    if engine_type == "autogluon_tabular":
        return _invoke_autogluon_artifact(deployment_id, target, body)

    question = body.question or body.query
    if not question:
        raise HTTPException(status_code=422, detail="Provide 'question' or 'query'.")

    deployment = _ensure_autorag_runner_for_identifier(deployment_id)
    runner = deployment["runner"]

    try:
        result = runner.run(question, result_column=body.result_column)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AutoRAG runner invocation failed: {_exception_chain_message(exc)}",
        ) from exc

    return {
        "deployment_id": deployment_id,
        "deployment": _deployment_without_runner(deployment),
        "question": question,
        "result": _json_safe(result),
        "invoked_at": _utc_now(),
    }


def _run_orchestrator_background(orch_id: str, request: dict[str, Any]) -> None:
    """Thread target: runs the full orchestrator synchronously."""
    from vectorforge_v1.orchestrator.runner import run_orchestrator

    session_id = str(request.get("session_id") or request.get("sessionId") or request.get("id") or orch_id)
    run_id = str(request.get("_vectorforge_run_id") or _new_orchestrator_run_id())
    request["_vectorforge_run_id"] = run_id
    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id]["status"] = "running"
        _ORCH_RUNS[orch_id]["run_id"] = run_id
    _write_session_meta(session_id, {"orch_id": orch_id, "status": "running"})

    try:
        result = run_orchestrator(request, work_dir=str(_RUNS_DIR / orch_id))
        autorag_result = _autorag_problem_result(result) or {}
        with _ORCH_LOCK:
            _ORCH_RUNS[orch_id].update({
                "status": result.get("status", "completed"),
                "result": result,
                "completed_at": _utc_now(),
            })
        _write_session_meta(
            session_id,
            {
                "orch_id": orch_id,
                "run_id": result.get("run_id"),
                "status": result.get("status", "completed"),
                "autorag_designer_run_id": autorag_result.get("designer_run_id"),
                "autorag_designer_run_dir": autorag_result.get("designer_run_dir"),
            },
        )
    except Exception as exc:
        with _ORCH_LOCK:
            _ORCH_RUNS[orch_id].update({
                "status": "failed",
                "error": str(exc),
                "completed_at": _utc_now(),
            })
        _write_session_meta(session_id, {"orch_id": orch_id, "status": "failed", "error": str(exc)})


# ── POST /orchestrate ─────────────────────────────────────────────────────────

@app.post("/orchestrate", tags=["orchestrate"])
def trigger_orchestrator(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Trigger a full VectorForge orchestration run.

    Accepts the standard orchestrator request body and dispatches each
    ml_problem to the appropriate designer (autogluon or autorag).
    Runs asynchronously — poll GET /orchestrate/{orch_id} for status.

    Example body:
    ```json
    {
      "business_problem": "Predict customer churn",
      "domain": "telecom",
      "num_round": 2,
      "max_experiment_per_round": 2,
      "ml_problems": [
        {
          "id": "churn_classification",
          "category": "traditional",
          "engine": "autogluon",
          "description": "Binary churn prediction",
          "business_kpis": ["Reduce churn while keeping outreach efficient"],
          "dataset": {
            "source": { "local_path": "runs/run_20260609_092649_745b2e10/input/dataset.csv" },
            "target_column": { "inferred_name": "Churn" }
          }
        }
      ]
    }
    ```

    For an AutoRAG problem, set `"category": "genai"` and `"engine": "autorag"`,
    and use `"dataset": { "source": { "local_path": "<path/to/docs/dir>" } }`.
    """
    orch_id = _new_orch_id()
    session_id = str(request.get("session_id") or request.get("sessionId") or request.get("id") or orch_id)
    run_id = _new_orchestrator_run_id()
    request["session_id"] = session_id
    request["_vectorforge_run_id"] = run_id
    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id] = {
            "orch_id": orch_id,
            "run_id": run_id,
            "status": "queued",
            "started_at": _utc_now(),
            "session_id": session_id,
            "request": request,
        }
    _write_session_meta(session_id, {"orch_id": orch_id, "status": "queued"})

    background_tasks.add_task(_run_orchestrator_background, orch_id, request)

    return {
        "orch_id": orch_id,
        "run_id": run_id,
        "session_id": session_id,
        "status": "queued",
        "poll_url": f"/orchestrate/{orch_id}",
        "started_at": _ORCH_RUNS[orch_id]["started_at"],
    }


# ── POST /orchestrate/from-session/{session_id} ───────────────────────────────

@app.post("/orchestrate/from-session/{session_id}", tags=["orchestrate"])
async def trigger_orchestrator_from_session(
    session_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Trigger an orchestration run from a Redis-stored conversation output.

    A conversation client writes the orchestrator request body to
    `vforge:conv:{session_id}` (session_id = "{user_id}_{workspace_id}_{project_id}",
    e.g. f1050d64_622614c6_d172aafc). This endpoint reads that key, parses the
    JSON, and dispatches it through the same machinery as POST /orchestrate.

    Returns immediately with an orch_id — poll GET /orchestrate/{orch_id} for status.
    """
    from vectorforge_v1.orchestrator.redis_store import get_session_output

    _load_env_files()
    try:
        request = await get_session_output(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface connection/read errors as 503
        raise HTTPException(status_code=503, detail=f"Redis read failed: {exc!s}") from exc

    if request is None:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation output found at vforge:conv:{session_id}",
        )
    request["session_id"] = session_id

    orch_id = _new_orch_id()
    run_id = _new_orchestrator_run_id()
    request["_vectorforge_run_id"] = run_id
    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id] = {
            "orch_id": orch_id,
            "run_id": run_id,
            "status": "queued",
            "started_at": _utc_now(),
            "session_id": session_id,
            "request": request,
        }
    _write_session_meta(session_id, {"orch_id": orch_id, "status": "queued"})

    background_tasks.add_task(_run_orchestrator_background, orch_id, request)

    return {
        "orch_id": orch_id,
        "run_id": run_id,
        "session_id": session_id,
        "status": "queued",
        "poll_url": f"/orchestrate/{orch_id}",
        "started_at": _ORCH_RUNS[orch_id]["started_at"],
    }


# ── GET /orchestrate/{orch_id} ────────────────────────────────────────────────

@app.get("/orchestrate/{orch_id}", tags=["orchestrate"])
def get_orchestrator_run(orch_id: str) -> dict[str, Any]:
    """
    Poll the status of an orchestration run.

    Returns the run status, and — when completed — the full result dict
    including `problem_results` with each designer's `designer_run_id` and
    `designer_run_dir`. The path id may be either the returned `orch_id` or
    the original conversational `session_id`.
    """
    _load_env_files()
    with _ORCH_LOCK:
        run = _ORCH_RUNS.get(orch_id)

    if not run:
        summary = _summary_from_orch_id(orch_id)
        if summary:
            return {"orch_id": orch_id, "source": "disk", **summary}

        session_run = _orchestrator_run_for_session(orch_id)
        if session_run:
            session_run.setdefault("requested_id", orch_id)
            return session_run

        raise HTTPException(status_code=404, detail=f"Orchestrator run '{orch_id}' not found")

    return dict(run)


# ── GET /sessions/{session_id}/experiment-results ────────────────────────────

@app.get("/sessions/{session_id}/experiment-results", tags=["experiment-results"])
def get_session_experiment_results(
    session_id: str,
    after: str = Query("0-0"),
    count: int = Query(100, ge=1, le=500),
    block_ms: int = Query(0, ge=0, le=30000),
) -> dict[str, Any]:
    """
    Poll Redis Stream-backed experiment updates for a frontend session.

    The frontend should start with after=0-0, then send the returned cursor
    on subsequent polls. The cursor advances to the last stream entry inspected,
    even if some entries are for other sessions.
    """
    _load_env_files()
    redis_url = os.environ.get("VECTORFORGE_REDIS_URL")
    stream = _redis_key("experiments:results")
    if not redis_url:
        raise HTTPException(status_code=503, detail="VECTORFORGE_REDIS_URL is not configured.")

    try:
        import redis

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        xread_kwargs: dict[str, Any] = {"count": count}
        if block_ms > 0:
            xread_kwargs["block"] = block_ms
        rows = client.xread({stream: after}, **xread_kwargs)
    except Exception as exc:  # noqa: BLE001 - surface Redis/network errors to the client.
        raise HTTPException(status_code=503, detail=f"Redis stream read failed: {exc!s}") from exc

    cursor = after
    events: list[dict[str, Any]] = []
    for _, messages in rows:
        for message_id, fields in messages:
            cursor = message_id
            if fields.get("session_id") != session_id:
                continue
            events.append(
                {
                    "id": message_id,
                    "payload": _decode_stream_payload(fields),
                }
            )

    return {
        "session_id": session_id,
        "cursor": cursor,
        "stream": stream,
        "events": events,
        "error": None,
    }


# ── POST /sessions/{session_id}/autorag/deploy ───────────────────────────────

@app.post("/sessions/{session_id}/autorag/deploy", tags=["deploy"])
def deploy_session_autorag(
    session_id: str,
    body: SessionAutoRagDeployRequest | None = None,
) -> dict[str, Any]:
    """
    Resolve the AutoRAG designer run produced for this session and load
    AutoRAG's in-process Runner for the best trial folder.
    """
    body = body or SessionAutoRagDeployRequest()
    resolved = _resolve_autorag_run_for_session(session_id)
    resolved["session_id"] = session_id
    return _deploy_autorag_runner(session_id, resolved, body, write_session_meta=True)


@app.post("/runs/{run_id}/autorag/deploy", tags=["deploy"])
def deploy_run_autorag(
    run_id: str,
    body: SessionAutoRagDeployRequest | None = None,
) -> dict[str, Any]:
    """
    Resolve an AutoRAG designer run from a run_id and load AutoRAG's
    in-process Runner. The run_id can be the orchestrator run_id or the
    AutoRAG designer run_id.
    """
    body = body or SessionAutoRagDeployRequest()
    resolved = _resolve_autorag_run_for_run_id(run_id)
    resolved["run_id"] = run_id
    return _deploy_autorag_runner(run_id, resolved, body, write_session_meta=False)


@app.post("/sessions/{session_id}/autorag/invoke", tags=["deploy"])
def invoke_session_autorag(session_id: str, body: AutoRagInvokeRequest) -> dict[str, Any]:
    return _autorag_invoke(session_id, body)


@app.post("/runs/{run_id}/autorag/invoke", tags=["deploy"])
def invoke_run_autorag(run_id: str, body: AutoRagInvokeRequest) -> dict[str, Any]:
    return _autorag_invoke(run_id, body)


@app.get("/sessions/{session_id}/autorag/input-schema", tags=["deploy"])
def get_session_autogluon_input_schema(session_id: str) -> dict[str, Any]:
    return _read_autogluon_artifact_io(session_id)


@app.get("/runs/{run_id}/autorag/input-schema", tags=["deploy"])
def get_run_autogluon_input_schema(run_id: str) -> dict[str, Any]:
    return _read_autogluon_artifact_io(run_id)


@app.get("/sessions/{session_id}/autorag/deploy/status", tags=["deploy"])
def get_session_autorag_deploy_status(session_id: str) -> dict[str, Any]:
    with _AUTORAG_DEPLOY_LOCK:
        deployment = _AUTORAG_DEPLOYS.get(session_id)
        if not deployment:
            meta = _read_session_meta(session_id)
            if meta.get("autorag_runner_trial_dir"):
                return {
                    "session_id": session_id,
                    "status": meta.get("autorag_runner_status", "unknown"),
                    "trial_dir": meta.get("autorag_runner_trial_dir"),
                    "source": "redis",
                }
            raise HTTPException(status_code=404, detail=f"No AutoRAG runner found for session '{session_id}'.")

    return _autorag_deploy_status(
        session_id,
        not_found_detail=f"No AutoRAG runner found for session '{session_id}'.",
    )


@app.get("/runs/{run_id}/autorag/deploy/status", tags=["deploy"])
def get_run_autorag_deploy_status(run_id: str) -> dict[str, Any]:
    return _autorag_deploy_status(
        run_id,
        not_found_detail=f"No AutoRAG runner found for run_id '{run_id}'.",
    )


# ── GET /runs/{run_id}/artifact/download ─────────────────────────────────────

@app.get("/runs/{run_id}/artifact/download", tags=["artifact"])
def download_artifact_by_run_id(run_id: str) -> FileResponse:
    """
    Download the sealed artifact zip for any run_id — works for:

    - An autogluon designer run_id  (e.g. run_20260609_092649_745b2e10)
    - An autorag designer run_id    (e.g. run_20260609_092649_745b2e10_p1_autorag)
    - An orchestrator orch_id       (returns the first artifact found under its designers)

    Generates the artifact on demand if the completed designer run has not
    already produced a zip.
    """
    zip_path = _ensure_artifact_zip(run_id)
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_path.name,
        headers={"Content-Disposition": f'attachment; filename="{zip_path.name}"'},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vectorforge-v1"}
