from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from vectorforge_v1.artifact_forge.config import get_settings
from vectorforge_v1.artifact_forge.contract import SmokeResult
from vectorforge_v1.artifact_forge.narrative import author_narrative
from vectorforge_v1.artifact_forge.registry import get_artifact_generator
from vectorforge_v1.artifact_forge.sandbox.contract import get_smoke_runner


def generate_artifact(
    engine_type: str,
    *,
    run_id: str,
    winner: dict[str, Any],
    run_dir: Path,
) -> Path | None:
    try:
        return _generate(engine_type, run_id=run_id, winner=winner, run_dir=run_dir)
    except Exception as exc:
        try:
            _record_failure(run_id, run_dir, str(exc))
        except Exception:
            pass
        return None


def _generate(
    engine_type: str,
    *,
    run_id: str,
    winner: dict[str, Any],
    run_dir: Path,
) -> Path:
    settings = get_settings()

    manifest_facts: dict[str, Any] = {
        "engine_type": engine_type,
        "task": winner.get("task_type") or winner.get("task", "ml_task"),
        "primary_metric": winner.get("primary_metric", "unknown"),
        "primary_metric_value": winner.get("primary_metric_value") or winner.get("best_score"),
        "secondary_metrics": winner.get("secondary_metrics") or {},
        "runtime": {},
        "io_schema": {},
        "input_schema": [],
    }

    narrative, used_llm = author_narrative(manifest_facts)
    used_fallbacks = not used_llm

    generator = get_artifact_generator(engine_type)

    pkg_name = f"vectorforge_artifact_{run_id}"
    artifact_dir = run_dir / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{pkg_name}_") as tmp_dir:
        pkg_dir = Path(tmp_dir) / pkg_name

        generator.generate(
            run_id=run_id,
            winner=winner,
            run_dir=run_dir,
            out_dir=pkg_dir,
            narrative=narrative,
        )

        manifest_path = pkg_dir / "manifest.json"
        manifest_data: dict[str, Any] = {}
        if manifest_path.exists():
            with manifest_path.open(encoding="utf-8") as f:
                manifest_data = json.load(f)

        smoke_runner = get_smoke_runner()
        try:
            smoke_result = smoke_runner.run(
                package_dir=pkg_dir,
                depth=settings.smoke_depth,
            )
        except NotImplementedError as exc:
            smoke_result = SmokeResult(
                status="skipped",
                degraded_reason=str(exc),
            )
        except Exception as exc:
            smoke_result = SmokeResult(
                status="skipped",
                degraded_reason=f"Smoke runner error: {exc!s}",
            )

        if smoke_result.status == "failed":
            from vectorforge_v1.artifact_forge.narrative import _synthesize_sample
            synth_sample = _synthesize_sample(
                manifest_data.get("input_schema", []),
                manifest_data.get("io_schema", {}),
                engine_type,
            )
            sample_input_path = pkg_dir / "sample_input.json"
            sample_input_path.write_text(json.dumps(synth_sample, indent=2), encoding="utf-8")
            used_fallbacks = True

        manifest_data["smoke_status"] = smoke_result.status
        artifact_status = "completed_with_fallbacks" if used_fallbacks else "completed"
        manifest_data["artifact_status"] = artifact_status

        from vectorforge_v1.artifact_forge.packager import atomic_write_json, seal_zip
        atomic_write_json(manifest_path, manifest_data)

        staged_zip_path = seal_zip(pkg_dir)
        final_zip_path = artifact_dir / staged_zip_path.name
        shutil.copy2(staged_zip_path, final_zip_path)

    _record_success(
        run_id,
        run_dir,
        str(final_zip_path),
        smoke_result.status,
        artifact_status,
    )

    return final_zip_path


def _record_success(
    run_id: str,
    run_dir: Path,
    zip_path: str,
    smoke_status: str,
    artifact_status: str,
) -> None:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return
    try:
        with status_path.open(encoding="utf-8") as f:
            status_data = json.load(f)
        status_data["artifact_zip_path"] = zip_path
        status_data["artifact_smoke_status"] = smoke_status
        status_data["artifact_status"] = artifact_status
        from vectorforge_v1.artifact_forge.packager import atomic_write_json
        atomic_write_json(status_path, status_data)
    except Exception:
        pass


def _record_failure(run_id: str, run_dir: Path, error: str) -> None:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return
    try:
        with status_path.open(encoding="utf-8") as f:
            status_data = json.load(f)
        status_data["artifact_status"] = "failed"
        status_data["artifact_error"] = error
        from vectorforge_v1.artifact_forge.packager import atomic_write_json
        atomic_write_json(status_path, status_data)
    except Exception:
        pass
