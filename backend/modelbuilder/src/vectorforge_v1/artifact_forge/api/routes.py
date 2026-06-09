"""
artifact_forge API — exposes the LangGraph artifact-forge workflow as REST endpoints.

Endpoints
─────────
POST /artifact-forge/runs/{run_id}/trigger
    Kick off (or re-kick) artifact generation for a completed research run.
    Accepts optional override fields in the JSON body.
    Returns immediately with job_id (= run_id used as LangGraph thread_id).

GET  /artifact-forge/runs/{run_id}/status
    Current graph state: artifact_status, smoke_status, events list, zip_path.

GET  /artifact-forge/runs/{run_id}/stream
    Server-Sent Events stream of graph task events (node start / finish).
    One JSON line per event; stream ends when graph reaches END.

GET  /artifact-forge/runs/{run_id}/download
    Download the sealed zip (once available).

GET  /artifact-forge/workflow/mermaid
    Returns the Mermaid diagram source for the artifact-forge graph.

POST /artifact-forge/runs/{run_id}/invoke
    Synchronous blocking invocation — returns the final state JSON.
    Intended for quick smoke-tests and CI; not for production workflows.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from vectorforge_v1.artifact_forge.artifact_resolver import ensure_artifact_zip_for_run, find_artifact_zip_in_run_dir
from vectorforge_v1.artifact_forge.workflow.graph import artifact_forge_graph
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore

load_dotenv()

router = APIRouter(prefix="/artifact-forge", tags=["artifact-forge"])


# ─── GET /health ─────────────────────────────────────────────────────────────

@router.get("/health")
def artifact_forge_health() -> dict[str, Any]:
    """
    Health check for the artifact-forge subsystem.

    Reports whether the Docker CLI is available and the daemon is reachable,
    so callers can verify deploy readiness before POSTing credentials.
    """
    docker_bin = shutil.which("docker")
    docker_available = False
    docker_detail = "docker CLI not found on PATH"
    if docker_bin:
        try:
            proc = subprocess.run(
                [docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=10,
            )
            docker_available = proc.returncode == 0
            docker_detail = (
                f"docker {proc.stdout.strip()}" if docker_available
                else (proc.stderr.strip() or "docker daemon not reachable")
            )
        except Exception as exc:  # noqa: BLE001 — health must never raise
            docker_detail = f"docker check failed: {exc!s}"

    return {
        "status": "ok",
        "service": "artifact-forge",
        "docker_available": docker_available,
        "docker_detail": docker_detail,
    }


# ─── helpers ────────────────────────────────────────────────────────────────

def _graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _winner_from_recommendation(run_id: str, store: ArtifactStore) -> dict[str, Any]:
    rec_path = store.run_dir(run_id) / "reports" / "final_recommendation.json"
    if not rec_path.exists():
        raise HTTPException(status_code=404, detail="final_recommendation.json not found — run not completed")
    rec = store.read_json(rec_path)
    return {
        "experiment_id":        rec.get("best_experiment_id"),
        "primary_metric":       rec.get("primary_metric"),
        "primary_metric_value": rec.get("best_score"),
        "secondary_metrics":    rec.get("secondary_metrics", {}),
        "model_path":           rec.get("winning_model_path"),
        "model_manifest_path":  rec.get("winning_model_manifest_path"),
        "holdout_metrics_path": rec.get("holdout_metrics_path"),
        "winning_config_yaml_path": rec.get("winning_config_yaml_path"),
        "corpus_path":          str(store.run_dir(run_id) / "corpus.parquet"),
    }


def _require_status(run_id: str, allowed: set[str]) -> None:
    store = ArtifactStore()
    try:
        current = store.read_status(run_id).get("status")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if current not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Run is '{current}'; artifact-forge requires one of {sorted(allowed)}",
        )


def _initial_state(run_id: str, engine_type: str, winner: dict, run_dir: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "engine_type": engine_type,
        "winner": winner,
        "run_dir": run_dir,
        "events": [],
    }


def _run_graph_background(run_id: str, initial_state: dict) -> None:
    """Thread target: invoke graph to completion (blocking, in its own thread)."""
    try:
        artifact_forge_graph.invoke(initial_state, _graph_config(run_id), version="v2")
    except Exception as exc:
        store = ArtifactStore()
        run_dir = store.run_dir(run_id)
        status_path = run_dir / "status.json"
        if status_path.exists():
            try:
                data = store.read_json(status_path)
                data["artifact_status"] = "failed"
                data["artifact_error"] = str(exc)
                store.write_json(status_path, data)
            except Exception:
                pass


# ─── POST /trigger ───────────────────────────────────────────────────────────

@router.post("/runs/{run_id}/trigger")
def trigger_artifact_forge(
    run_id: str,
    background_tasks: BackgroundTasks,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Start (or re-start) artifact generation for a completed research run.

    Optional JSON body:
      { "engine_type": "autogluon_tabular" | "autorag",
        "winner": { ... override winner fields ... } }
    """
    _require_status(run_id, {"completed"})

    store = ArtifactStore()
    body = body or {}
    engine_type: str = body.get("engine_type", "autogluon_tabular")
    winner: dict = body.get("winner") or _winner_from_recommendation(run_id, store)
    run_dir = str(store.run_dir(run_id))

    initial_state = _initial_state(run_id, engine_type, winner, run_dir)
    background_tasks.add_task(_run_graph_background, run_id, initial_state)

    return {
        "run_id": run_id,
        "job_id": run_id,
        "engine_type": engine_type,
        "status": "artifact_generation_started",
        "stream_url": f"/artifact-forge/runs/{run_id}/stream",
        "status_url": f"/artifact-forge/runs/{run_id}/status",
    }


# ─── GET /status ─────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/status")
def get_artifact_status(run_id: str) -> dict[str, Any]:
    """
    Return the current LangGraph checkpoint state for this run_id.
    Falls back to status.json fields if the graph hasn't started yet.
    """
    store = ArtifactStore()
    try:
        store.read_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Try reading from the live graph checkpoint first
    graph_state = artifact_forge_graph.get_state(_graph_config(run_id))
    if graph_state and graph_state.values:
        values = graph_state.values
        return {
            "run_id": run_id,
            "source": "graph_checkpoint",
            "artifact_status":   values.get("artifact_status"),
            "smoke_status":      values.get("smoke_status"),
            "zip_path":          values.get("zip_path"),
            "artifact_error":    values.get("artifact_error"),
            "used_llm_narrative": values.get("used_llm_narrative"),
            "events":            values.get("events", []),
            "next":              list(graph_state.next),
        }

    # Fallback: read status.json artifact fields
    status_data = store.read_status(run_id)
    return {
        "run_id": run_id,
        "source": "status_json",
        "artifact_status":   status_data.get("artifact_status"),
        "smoke_status":      status_data.get("artifact_smoke_status"),
        "zip_path":          status_data.get("artifact_zip_path"),
        "artifact_error":    status_data.get("artifact_error"),
        "events":            [],
    }


# ─── GET /stream  (SSE) ──────────────────────────────────────────────────────

@router.get("/runs/{run_id}/stream")
def stream_artifact_events(run_id: str) -> StreamingResponse:
    """
    Server-Sent Events stream.  Each event is a JSON line:
      {"type": "task_start"|"task_finish"|"error", "node": "...", "data": {...}}

    Attach with:
      curl -N http://localhost:8000/artifact-forge/runs/{run_id}/stream
    """
    store = ArtifactStore()
    try:
        store.read_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _event_generator():
        try:
            for chunk in artifact_forge_graph.stream(
                None,                          # resume from checkpoint; input=None
                _graph_config(run_id),
                stream_mode="tasks",
                version="v2",
            ):
                if chunk.get("type") == "tasks":
                    for task in (chunk.get("data") or []):
                        yield f"data: {json.dumps({'type': 'task', 'task': task})}\n\n"
                elif chunk.get("type") in ("task_results", "debug"):
                    yield f"data: {json.dumps({'type': chunk['type'], 'data': chunk.get('data')})}\n\n"
        except StopIteration:
            pass
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


# ─── GET /download ───────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/download")
def download_artifact(run_id: str) -> FileResponse:
    """Download the sealed artifact zip, generating it on demand if needed."""
    store = ArtifactStore()
    try:
        store.read_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run_dir = store.run_dir(run_id)
    zip_path = find_artifact_zip_in_run_dir(run_dir)
    if not zip_path:
        try:
            zip_path = ensure_artifact_zip_for_run(run_id=run_id, run_dir=run_dir)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Artifact generation failed: {exc}") from exc

    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


# ─── POST /runs/{folder_id}/deploy ───────────────────────────────────────────

class DeployRequest(BaseModel):
    # AWS account/region — consumed by deploy.sh
    aws_account_id: str | None = None
    aws_region: str = "us-east-1"
    # AWS credentials — consumed by the aws CLI inside deploy.sh
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    # behavior
    allow_deploy: bool = True
    force_rebuild: bool = False


def _aws_env_from_request(body: DeployRequest) -> dict[str, str]:
    env: dict[str, str] = {}
    if body.aws_account_id:
        env["AWS_ACCOUNT_ID"] = body.aws_account_id
    if body.aws_region:
        env["AWS_REGION"] = body.aws_region
    if body.aws_access_key_id:
        env["AWS_ACCESS_KEY_ID"] = body.aws_access_key_id
    if body.aws_secret_access_key:
        env["AWS_SECRET_ACCESS_KEY"] = body.aws_secret_access_key
    if body.aws_session_token:
        env["AWS_SESSION_TOKEN"] = body.aws_session_token
    return env


def _deploy_sidecar(zip_path: Path) -> Path:
    return zip_path.parent / "deploy_result.json"


def _write_deploy_result(zip_path: Path, data: dict[str, Any]) -> None:
    try:
        _deploy_sidecar(zip_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _run_deploy_background(
    folder_id: str,
    zip_path: Path,
    env_overrides: dict[str, str],
    *,
    allow_deploy: bool,
    force_rebuild: bool,
) -> None:
    """Thread target: build + (optionally) deploy, then persist the sidecar.

    AWS credentials live only in env_overrides for this task's lifetime — they
    are never written to the sidecar (DeployResult excludes them) and are
    garbage-collected when the task returns.
    """
    from vectorforge_v1.artifact_forge.deploy.docker_runner import DockerDeployRunner

    runner = DockerDeployRunner(
        run_id=folder_id,
        run_dir=zip_path.parent,
        allow_deploy=allow_deploy,
        force_rebuild=force_rebuild,
    )
    result = runner.run(zip_path=zip_path, env_overrides=env_overrides)
    _write_deploy_result(zip_path, result.to_dict())


@router.post("/runs/{folder_id}/deploy")
def deploy_artifact_endpoint(
    folder_id: str,
    background_tasks: BackgroundTasks,
    body: DeployRequest | None = None,
) -> dict[str, Any]:
    """
    Build the Docker image from the artifact folder's sealed zip and, when AWS
    credentials are supplied in the body, run deploy.sh (build → ECR → CloudFormation).

    NOTE: this endpoint accepts AWS credentials in the request body — serve over
    TLS only. Credentials are injected into the deploy subprocess environment for
    the duration of the run and are never persisted or echoed back.

    Body (all optional):
      { "aws_account_id": "123456789012",
        "aws_region": "us-east-1",
        "aws_access_key_id": "...",
        "aws_secret_access_key": "...",
        "aws_session_token": "...",     # for STS/assumed-role creds
        "allow_deploy": true,
        "force_rebuild": false }

    deploy.sh runs only when allow_deploy AND aws_account_id AND aws_access_key_id
    AND aws_secret_access_key are all present; otherwise the image is built only.

    Returns immediately — poll GET /runs/{folder_id}/deploy/status for the result.
    """
    from vectorforge_v1.artifact_forge.deploy.resolver import resolve_artifact_zip

    body = body or DeployRequest()
    try:
        zip_path = resolve_artifact_zip(folder_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    env_overrides = _aws_env_from_request(body)
    _write_deploy_result(zip_path, {"status": "running", "run_id": folder_id})

    background_tasks.add_task(
        _run_deploy_background,
        folder_id,
        zip_path,
        env_overrides,
        allow_deploy=body.allow_deploy,
        force_rebuild=body.force_rebuild,
    )

    return {
        "folder_id": folder_id,
        "zip_path": str(zip_path),
        "status": "deploy_started",
        "deploy_status_url": f"/artifact-forge/runs/{folder_id}/deploy/status",
    }


# ─── GET /runs/{folder_id}/deploy/status ─────────────────────────────────────

@router.get("/runs/{folder_id}/deploy/status")
def get_deploy_status(folder_id: str) -> dict[str, Any]:
    """Return the deploy result for this folder (built|deployed|failed|running)."""
    from vectorforge_v1.artifact_forge.deploy.resolver import resolve_artifact_zip

    try:
        zip_path = resolve_artifact_zip(folder_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    sidecar = _deploy_sidecar(zip_path)
    if not sidecar.exists():
        return {"folder_id": folder_id, "status": "not_started"}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read deploy result: {exc}") from exc
    return {"folder_id": folder_id, **data}


# ─── GET /workflow/mermaid ───────────────────────────────────────────────────

@router.get("/workflow/mermaid", response_class=PlainTextResponse)
def get_workflow_mermaid() -> str:
    """Return the Mermaid diagram source for the artifact-forge graph."""
    return artifact_forge_graph.get_graph().draw_mermaid()


# ─── POST /invoke  (synchronous, blocking) ───────────────────────────────────

@router.post("/runs/{run_id}/invoke")
def invoke_artifact_forge(
    run_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Synchronous blocking invocation — runs the full graph in the request thread.
    Returns the final state.  Use for smoke-tests and CI.

    Required JSON body:
      { "engine_type": "autogluon_tabular",
        "winner": { ... } }   ← or omit to auto-read from final_recommendation.json
    """
    _require_status(run_id, {"completed"})

    store = ArtifactStore()
    body = body or {}
    engine_type: str = body.get("engine_type", "autogluon_tabular")
    winner: dict = body.get("winner") or _winner_from_recommendation(run_id, store)
    run_dir = str(store.run_dir(run_id))

    initial_state = _initial_state(run_id, engine_type, winner, run_dir)
    result = artifact_forge_graph.invoke(initial_state, _graph_config(run_id), version="v2")

    values = getattr(result, "value", result) or {}
    return {
        "run_id":           run_id,
        "artifact_status":  values.get("artifact_status"),
        "smoke_status":     values.get("smoke_status"),
        "zip_path":         values.get("zip_path"),
        "artifact_error":   values.get("artifact_error"),
        "used_llm_narrative": values.get("used_llm_narrative"),
        "events":           values.get("events", []),
    }
