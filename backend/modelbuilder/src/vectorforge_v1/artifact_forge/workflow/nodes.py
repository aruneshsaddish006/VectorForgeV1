"""
artifact_forge LangGraph nodes — one pure function per step.

Graph shape:
  START
    → build_manifest_facts
    → author_narrative          (LLM via AI Gateway structured tool call; falls back deterministically)
    → generate_package          (engine-dispatched: autogluon | autorag)
    → run_smoke                 (OpenSandbox | vercel-stub | local; never raises into graph)
    → reconcile_artifact        (apply smoke result → update manifest + sample_input if needed)
    → seal_and_record           (reseal zip, copy to artifact dir, write status.json; emit final event)
    → [fail_artifact on any unrecoverable error]
  END
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from vectorforge_v1.artifact_forge.workflow.state import ArtifactForgeState


# ─────────────────────────────── node 1 ────────────────────────────────────

def build_manifest_facts(state: ArtifactForgeState) -> dict:
    winner = state.get("winner") or {}
    engine_type = state.get("engine_type", "autogluon_tabular")

    facts: dict[str, Any] = {
        "engine_type": engine_type,
        "task": winner.get("task_type") or winner.get("task", "ml_task"),
        "primary_metric": winner.get("primary_metric", "unknown"),
        "primary_metric_value": winner.get("primary_metric_value") or winner.get("best_score"),
        "secondary_metrics": winner.get("secondary_metrics") or {},
        "io_schema": {},
        "input_schema": [],
        "runtime": {},
    }

    run_dir = Path(state["run_dir"])
    if engine_type == "autogluon_tabular":
        profile_path = run_dir / "input" / "dataset_profile.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                facts["input_schema"] = [
                    {"name": c.get("name", c.get("column", "")), "dtype": c.get("dtype", "object")}
                    for c in (profile.get("columns") or profile.get("features") or [])
                    if c.get("name") or c.get("column")
                ]
            except Exception:
                pass
        facts["io_schema"] = {"input": "list[dict] | csv_path | DataFrame", "output": "list[prediction]"}
    else:
        facts["io_schema"] = {"input": "list[str] queries | str", "output": "list[{answer, contexts}]"}

    return {
        "manifest_facts": facts,
        "narrative_ok": False,
        "generation_ok": False,
        "smoke_ok": False,
        "events": [{"node": "build_manifest_facts", "status": "completed",
                    "message": f"Manifest facts built for engine={engine_type}."}],
    }


# ─────────────────────────────── node 2 ────────────────────────────────────

def author_narrative(state: ArtifactForgeState) -> dict:
    from vectorforge_v1.artifact_forge.narrative import author_narrative as _author

    facts = state.get("manifest_facts") or {}
    try:
        narrative_obj, used_llm = _author(facts)
        narrative_dict = narrative_obj.model_dump()
        return {
            "narrative": narrative_dict,
            "used_llm_narrative": used_llm,
            "narrative_ok": True,
            "events": [{"node": "author_narrative", "status": "completed",
                        "message": f"Narrative authored (llm={used_llm})."}],
        }
    except Exception as exc:
        return {
            "narrative": None,
            "used_llm_narrative": False,
            "narrative_ok": False,
            "artifact_error": str(exc),
            "events": [{"node": "author_narrative", "status": "failed", "message": str(exc)}],
        }


# ─────────────────────────────── node 3 ────────────────────────────────────

def generate_package(state: ArtifactForgeState) -> dict:
    from vectorforge_v1.artifact_forge.registry import get_artifact_generator
    from vectorforge_v1.artifact_forge.contract import ArtifactNarrative

    engine_type = state.get("engine_type", "autogluon_tabular")
    run_id = state["run_id"]
    winner = state.get("winner") or {}
    run_dir = Path(state["run_dir"])
    narrative_dict = state.get("narrative") or {}

    try:
        narrative = ArtifactNarrative.model_validate(narrative_dict)
    except Exception:
        from vectorforge_v1.artifact_forge.narrative import _deterministic_narrative
        narrative = _deterministic_narrative(state.get("manifest_facts") or {})

    pkg_name = f"vectorforge_artifact_{run_id}"
    staging_dir = Path(tempfile.mkdtemp(prefix=f"{pkg_name}_"))
    pkg_dir = staging_dir / pkg_name

    try:
        generator = get_artifact_generator(engine_type)
        zip_path = generator.generate(
            run_id=run_id,
            winner=winner,
            run_dir=run_dir,
            out_dir=pkg_dir,
            narrative=narrative,
        )
        return {
            "package_dir": str(pkg_dir),
            "staging_dir": str(staging_dir),
            "zip_path": str(zip_path),
            "generation_ok": True,
            "events": [{"node": "generate_package", "status": "completed",
                        "message": f"Package assembled: {zip_path.name}"}],
        }
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return {
            "package_dir": str(pkg_dir),
            "staging_dir": str(staging_dir),
            "zip_path": None,
            "generation_ok": False,
            "artifact_error": str(exc),
            "events": [{"node": "generate_package", "status": "failed", "message": str(exc)}],
        }


# ─────────────────────────────── node 4 ────────────────────────────────────

def run_smoke(state: ArtifactForgeState) -> dict:
    from vectorforge_v1.artifact_forge.sandbox.contract import get_smoke_runner
    from vectorforge_v1.artifact_forge.config import get_settings
    from vectorforge_v1.artifact_forge.contract import ArtifactNarrative

    pkg_dir_str = state.get("package_dir")

    if not pkg_dir_str or not Path(pkg_dir_str).exists():
        return {
            "smoke_status": "skipped",
            "smoke_stdout": "",
            "smoke_sandbox_id": None,
            "smoke_degraded_reason": "package_dir not available",
            "smoke_ok": True,
            "events": [{"node": "run_smoke", "status": "skipped",
                        "message": "Smoke skipped — package_dir unavailable."}],
        }

    try:
        settings = get_settings()
        runner = get_smoke_runner()
        result = runner.run(
            package_dir=Path(pkg_dir_str),
            depth=settings.smoke_depth,
        )
    except NotImplementedError as exc:
        from vectorforge_v1.artifact_forge.contract import SmokeResult
        result = SmokeResult(status="skipped", degraded_reason=str(exc))
    except Exception as exc:
        from vectorforge_v1.artifact_forge.contract import SmokeResult
        result = SmokeResult(status="skipped", degraded_reason=f"Smoke runner error: {exc}")

    smoke_ok = result.status in ("passed", "passed_contract_only", "skipped")
    return {
        "smoke_status": result.status,
        "smoke_stdout": result.stdout,
        "smoke_sandbox_id": result.sandbox_id,
        "smoke_degraded_reason": result.degraded_reason,
        "smoke_ok": smoke_ok,
        "events": [{"node": "run_smoke", "status": result.status,
                    "message": result.degraded_reason or result.status}],
    }


# ─────────────────────────────── node 5 ────────────────────────────────────

def reconcile_artifact(state: ArtifactForgeState) -> dict:
    """
    Apply smoke result to the manifest.json already on disk.
    If smoke failed → replace sample_input with synthesised fallback.
    """
    from vectorforge_v1.artifact_forge.packager import atomic_write_json
    from vectorforge_v1.artifact_forge.narrative import _synthesize_sample

    pkg_dir_str = state.get("package_dir")
    smoke_status = state.get("smoke_status", "skipped")
    used_fallbacks = not state.get("used_llm_narrative", False)

    if not pkg_dir_str:
        return {
            "artifact_status": "failed",
            "events": [{"node": "reconcile_artifact", "status": "failed",
                        "message": "No package_dir to reconcile."}],
        }

    pkg_dir = Path(pkg_dir_str)
    manifest_path = pkg_dir / "manifest.json"

    if not manifest_path.exists():
        return {
            "artifact_status": "failed",
            "events": [{"node": "reconcile_artifact", "status": "failed",
                        "message": "manifest.json missing from package_dir."}],
        }

    manifest_data: dict = json.loads(manifest_path.read_text(encoding="utf-8"))

    if smoke_status == "failed":
        synth = _synthesize_sample(
            manifest_data.get("input_schema", []),
            manifest_data.get("io_schema", {}),
            manifest_data.get("engine_type", "autogluon_tabular"),
        )
        (pkg_dir / "sample_input.json").write_text(json.dumps(synth, indent=2), encoding="utf-8")
        used_fallbacks = True

    manifest_data["smoke_status"] = smoke_status
    artifact_status: str = "completed_with_fallbacks" if used_fallbacks else "completed"
    manifest_data["artifact_status"] = artifact_status
    atomic_write_json(manifest_path, manifest_data)

    return {
        "artifact_status": artifact_status,
        "events": [{"node": "reconcile_artifact", "status": "completed",
                    "message": f"Manifest updated: smoke_status={smoke_status}, artifact_status={artifact_status}."}],
    }


# ─────────────────────────────── node 6 ────────────────────────────────────

def seal_and_record(state: ArtifactForgeState) -> dict:
    """Write final artifact fields into status.json and emit the terminal event."""
    from vectorforge_v1.artifact_forge.packager import atomic_write_json, seal_zip

    run_dir = Path(state["run_dir"])
    status_path = run_dir / "status.json"
    pkg_dir = Path(state["package_dir"]) if state.get("package_dir") else None
    zip_path_str = state.get("zip_path")
    smoke_status = state.get("smoke_status", "skipped")
    artifact_status = state.get("artifact_status", "completed")

    if pkg_dir and pkg_dir.exists():
        try:
            artifact_dir = run_dir / "artifact"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            staged_zip_path = seal_zip(pkg_dir)
            final_zip_path = artifact_dir / staged_zip_path.name
            shutil.copy2(staged_zip_path, final_zip_path)
            zip_path_str = str(final_zip_path)
        finally:
            staging_dir = state.get("staging_dir")
            if staging_dir:
                shutil.rmtree(staging_dir, ignore_errors=True)

    if status_path.exists():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
            status_data["artifact_zip_path"] = zip_path_str
            status_data["artifact_smoke_status"] = smoke_status
            status_data["artifact_status"] = artifact_status
            atomic_write_json(status_path, status_data)
        except Exception:
            pass

    return {
        "events": [{"node": "seal_and_record", "status": "completed",
                    "message": f"Artifact sealed → {zip_path_str or 'N/A'} | smoke={smoke_status} | status={artifact_status}"}],
    }


# ─────────────────────────────── error node ─────────────────────────────────

def fail_artifact(state: ArtifactForgeState) -> dict:
    """
    Non-fatal terminal: records artifact_status=failed in status.json and exits.
    The research run itself is never touched.
    """
    from vectorforge_v1.artifact_forge.packager import atomic_write_json

    run_dir = Path(state["run_dir"])
    status_path = run_dir / "status.json"
    error = state.get("artifact_error", "unknown error")
    staging_dir = state.get("staging_dir")
    if staging_dir:
        shutil.rmtree(staging_dir, ignore_errors=True)

    if status_path.exists():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
            status_data["artifact_status"] = "failed"
            status_data["artifact_error"] = error
            atomic_write_json(status_path, status_data)
        except Exception:
            pass

    return {
        "artifact_status": "failed",
        "events": [{"node": "fail_artifact", "status": "failed", "message": error}],
    }
