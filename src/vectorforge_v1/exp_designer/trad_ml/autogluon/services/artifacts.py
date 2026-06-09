from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings


ACTIVE_STATUSES = {
    "created",
    "awaiting_clarification",
    "profiling",
    "planning",
    "awaiting_confirmation",
    "queued",
    "running",
}

TERMINAL_STATUSES = {"completed", "failed"}


class ArtifactStore:
    def __init__(self, runs_dir: Path | None = None, staged_uploads_dir: Path | None = None) -> None:
        settings = get_settings()
        self.runs_dir = runs_dir or settings.runs_dir
        self.staged_uploads_dir = staged_uploads_dir or settings.staged_uploads_dir

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def create_pending_run(self, run_id: str) -> Path:
        run_dir = self.run_dir(run_id)
        for relative in ("input", "planning", "experiments", "reports"):
            (run_dir / relative).mkdir(parents=True, exist_ok=True)
        self.write_status(run_id, "created")
        return run_dir

    async def stage_upload(self, run_id: str, upload: UploadFile) -> Path:
        self.staged_uploads_dir.mkdir(parents=True, exist_ok=True)
        destination = self.staged_uploads_dir / f"{run_id}_{upload.filename or 'dataset.csv'}"
        with destination.open("wb") as out_file:
            while chunk := await upload.read(1024 * 1024):
                out_file.write(chunk)
        return destination

    def materialize_input(self, run_id: str, source_dataset_path: str, user_request: dict[str, Any]) -> Path:
        run_dir = self.create_pending_run(run_id)
        input_dir = run_dir / "input"
        dataset_path = input_dir / "dataset.csv"
        if not source_dataset_path:
            raise ValueError("dataset_path is required before creating run artifacts")
        shutil.copyfile(source_dataset_path, dataset_path)
        self.write_json(input_dir / "user_request.json", {**user_request, "dataset_path": str(dataset_path)})
        self.write_status(run_id, "created")
        return dataset_path

    def write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, default=str)
                handle.write("\n")
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path

    def read_json(self, path: Path) -> Any:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def write_status(self, run_id: str, status: str, extra: dict[str, Any] | None = None) -> Path:
        payload = {"run_id": run_id, "status": status}
        if extra:
            payload.update(extra)
        return self.write_json(self.run_dir(run_id) / "status.json", payload)

    def read_status(self, run_id: str) -> dict[str, Any]:
        status_path = self.run_dir(run_id) / "status.json"
        if not status_path.exists():
            raise FileNotFoundError(f"Run {run_id} does not exist")
        return self.read_json(status_path)

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for status_file in sorted(self.runs_dir.glob("*/status.json")):
            try:
                status = self.read_json(status_file)
            except json.JSONDecodeError:
                continue
            status["run_id"] = status.get("run_id") or status_file.parent.name
            status["run_dir"] = str(status_file.parent)
            status["is_active"] = status.get("status") in ACTIVE_STATUSES
            runs.append(status)
        return runs

    def list_active_runs(self) -> list[dict[str, Any]]:
        return [run for run in self.list_runs() if run.get("is_active")]

    def mark_active_runs_failed(self, reason: str) -> list[str]:
        failed_run_ids = []
        for run in self.list_active_runs():
            run_id = run["run_id"]
            self.write_status(run_id, "failed", {"error": reason, "previous_status": run.get("status")})
            failed_run_ids.append(run_id)
        return failed_run_ids

    def mark_run_failed(self, run_id: str, reason: str) -> Path:
        current_status = self.read_status(run_id).get("status")
        if current_status in TERMINAL_STATUSES:
            raise ValueError(f"Run {run_id} is already {current_status}")
        return self.write_status(run_id, "failed", {"error": reason, "previous_status": current_status})

    def has_active_run(self) -> bool:
        if not self.runs_dir.exists():
            return False
        return bool(self.list_active_runs())

    def write_leaderboard(self, run_id: str, rows: list[dict[str, Any]]) -> Path:
        path = self.run_dir(run_id) / "reports" / "leaderboard.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "round",
            "experiment_id",
            "status",
            "primary_metric",
            "primary_metric_value",
            "secondary_metrics",
            "holdout_metrics_path",
            "model_path",
            "model_manifest_path",
            "error_summary",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field) for field in fieldnames})
        return path

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
