from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict


class ArtifactForgeState(TypedDict, total=False):
    # --- inputs (required at graph entry) ---
    run_id: str
    engine_type: str                          # "autogluon_tabular" | "autorag"
    winner: dict                              # ExperimentResult / AutoRAG final_recommendation fields
    run_dir: str                              # str path so it serialises through checkpointer

    # --- intermediate ---
    manifest_facts: dict                      # structured context passed to narrative node
    narrative: dict                           # ArtifactNarrative serialised as dict
    used_llm_narrative: bool
    package_dir: str                          # path to assembled (pre-zip) package dir
    staging_dir: str                          # temp directory containing package_dir
    zip_path: str | None                      # sealed zip path; None means generation failed

    # --- smoke ---
    smoke_status: Literal["passed", "passed_contract_only", "failed", "skipped"]
    smoke_stdout: str
    smoke_sandbox_id: str | None
    smoke_degraded_reason: str | None

    # --- final ---
    artifact_status: Literal["completed", "completed_with_fallbacks", "failed"]
    artifact_error: str | None

    # --- routing flags ---
    narrative_ok: bool
    generation_ok: bool
    smoke_ok: bool                            # True = passed or passed_contract_only or skipped

    # --- accumulating ---
    events: Annotated[list[dict], operator.add]
