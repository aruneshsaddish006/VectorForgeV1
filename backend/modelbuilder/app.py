"""
app.py — VectorForge V1 unified FastAPI application.

Mounts all sub-routers and adds top-level orchestrator endpoints:

  POST /orchestrate          — trigger a full multi-problem run (autogluon or autorag)
  GET  /orchestrate/{run_id} — poll orchestrator run status

Artifact download (by orchestrator run_id or designer run_id):
  GET  /runs/{run_id}/artifact/download — generate on demand and download the sealed artifact zip

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
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
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

# Resolved path to the runs base directory (matches ArtifactStore default)
_RUNS_DIR = Path("runs")


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_files() -> None:
    for path in _candidate_env_paths():
        if path.exists():
            _load_env_file(path)


def _candidate_env_paths() -> list[Path]:
    app_root = Path(__file__).resolve().parent
    package_root = app_root / "src" / "vectorforge_v1"
    return [
        Path.cwd() / ".env",
        app_root / ".env",
        package_root / ".env",
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
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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


def _run_orchestrator_background(orch_id: str, request: dict[str, Any]) -> None:
    """Thread target: runs the full orchestrator synchronously."""
    from vectorforge_v1.orchestrator.runner import run_orchestrator

    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id]["status"] = "running"

    try:
        result = run_orchestrator(request, work_dir=str(_RUNS_DIR / orch_id))
        with _ORCH_LOCK:
            _ORCH_RUNS[orch_id].update({
                "status": result.get("status", "completed"),
                "result": result,
                "completed_at": _utc_now(),
            })
    except Exception as exc:
        with _ORCH_LOCK:
            _ORCH_RUNS[orch_id].update({
                "status": "failed",
                "error": str(exc),
                "completed_at": _utc_now(),
            })


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
    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id] = {
            "orch_id": orch_id,
            "status": "queued",
            "started_at": _utc_now(),
            "request": request,
        }

    background_tasks.add_task(_run_orchestrator_background, orch_id, request)

    return {
        "orch_id": orch_id,
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
    with _ORCH_LOCK:
        _ORCH_RUNS[orch_id] = {
            "orch_id": orch_id,
            "status": "queued",
            "started_at": _utc_now(),
            "session_id": session_id,
            "request": request,
        }

    background_tasks.add_task(_run_orchestrator_background, orch_id, request)

    return {
        "orch_id": orch_id,
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
    `designer_run_dir`.
    """
    with _ORCH_LOCK:
        run = _ORCH_RUNS.get(orch_id)

    if not run:
        # Fall back: check if a run directory was written to disk
        summary_path = _RUNS_DIR / orch_id / "reports" / "orchestrator_summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                return {"orch_id": orch_id, "source": "disk", **summary}
            except Exception:
                pass
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
