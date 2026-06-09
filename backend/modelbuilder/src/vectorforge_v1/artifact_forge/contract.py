from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ArtifactNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str
    sample_input: dict[str, Any] | list[Any]
    usage_walkthrough: str
    serving_notes: str
    retraining_notes: str
    caveats: list[str]


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_type: str
    task: str
    primary_metric: str
    primary_metric_value: float | None
    secondary_metrics: dict[str, float | int | None] = Field(default_factory=dict)
    io_schema: dict[str, str] = Field(default_factory=dict)
    input_schema: list[dict[str, Any]] = Field(default_factory=list)
    trained_at: str
    runtime: dict[str, Any] = Field(default_factory=dict)
    smoke_status: Literal["passed", "passed_contract_only", "failed", "skipped"] = "skipped"
    artifact_status: Literal["completed", "completed_with_fallbacks", "failed"] = "completed"


class SmokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "passed_contract_only", "failed", "skipped"]
    stdout: str = ""
    exit_code: int | None = None
    sandbox_id: str | None = None
    degraded_reason: str | None = None


@runtime_checkable
class ArtifactGenerator(Protocol):
    engine_type: str

    def generate(
        self,
        *,
        run_id: str,
        winner: dict[str, Any],
        run_dir: Path,
        out_dir: Path,
        narrative: ArtifactNarrative,
    ) -> Path: ...
