from __future__ import annotations

from vectorforge_v1.artifact_forge.workflow.state import ArtifactForgeState


def route_after_narrative(state: ArtifactForgeState) -> str:
    """If narrative failed entirely, go straight to failure — nothing to package."""
    return "generate_package" if state.get("narrative_ok") else "fail_artifact"


def route_after_generation(state: ArtifactForgeState) -> str:
    """If package couldn't be assembled (missing model, bad paths), fail fast."""
    return "run_smoke" if state.get("generation_ok") else "fail_artifact"


def route_after_smoke(state: ArtifactForgeState) -> str:
    """
    Smoke result is advisory — passed/skipped/contract-only all continue.
    Only a hard smoke_ok=False (which never happens by design) would reroute.
    """
    return "reconcile_artifact"


def route_after_reconcile(state: ArtifactForgeState) -> str:
    artifact_status = state.get("artifact_status", "completed")
    return "fail_artifact" if artifact_status == "failed" else "seal_and_record"
