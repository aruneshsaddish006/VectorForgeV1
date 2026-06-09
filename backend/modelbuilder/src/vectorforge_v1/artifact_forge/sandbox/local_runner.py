from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

from vectorforge_v1.artifact_forge.contract import SmokeResult


class LocalSubprocessRunner:
    def run(
        self,
        package_dir: Path,
        depth: Literal["full", "contract"] = "full",
    ) -> SmokeResult:
        infer_script = package_dir / "infer.py"
        sample_path = package_dir / "sample_input.json"

        if not infer_script.exists():
            return SmokeResult(
                status="skipped",
                degraded_reason="infer.py not found in package_dir",
            )

        if not sample_path.exists():
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            from vectorforge_v1.artifact_forge.narrative import _synthesize_sample

            sample_input = _synthesize_sample(
                manifest.get("input_schema", []),
                manifest.get("io_schema", {}),
                manifest.get("engine_type", "autogluon_tabular"),
            )
            sample_path.write_text(json.dumps(sample_input, indent=2), encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(infer_script), "--input", str(sample_path)],
                capture_output=True,
                text=True,
                cwd=str(package_dir),
                timeout=120,
            )
            stdout = result.stdout + result.stderr
            if result.returncode == 0:
                return SmokeResult(status="passed", stdout=stdout, exit_code=0)
            return SmokeResult(
                status="failed",
                stdout=stdout,
                exit_code=result.returncode,
                degraded_reason="infer.py returned non-zero exit code",
            )
        except subprocess.TimeoutExpired:
            return SmokeResult(
                status="skipped",
                degraded_reason="Local smoke run timed out after 120s",
            )
        except Exception as exc:
            return SmokeResult(
                status="skipped",
                degraded_reason=f"Local smoke error: {exc!s}",
            )
