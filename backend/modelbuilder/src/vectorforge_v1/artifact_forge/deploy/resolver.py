"""
Resolve a folder/run id to its sealed artifact zip.

Two-tier lookup so both the flat (current) and legacy-nested run layouts work:

  Tier 1 — flat:   ArtifactStore.run_dir(folder_id) → find / ensure the zip there.
  Tier 2 — search: recursive glob under runs_dir for a matching artifact zip,
                   covering the legacy orch_.../designers/.../artifact/*.zip shape.
"""
from __future__ import annotations

from pathlib import Path

from vectorforge_v1.artifact_forge.artifact_resolver import (
    ensure_artifact_zip_for_run,
    find_artifact_zip_in_run_dir,
)
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore


def resolve_artifact_zip(folder_id: str, *, store: ArtifactStore | None = None) -> Path:
    """
    Resolve a folder/run id to its sealed artifact zip path.

    Raises FileNotFoundError if no artifact zip can be found or generated.
    """
    store = store or ArtifactStore()

    # Tier 1 — flat layout: runs_dir/<folder_id>/
    run_dir = store.run_dir(folder_id)
    if run_dir.exists():
        existing = find_artifact_zip_in_run_dir(run_dir)
        if existing:
            return existing
        try:
            return ensure_artifact_zip_for_run(run_id=folder_id, run_dir=run_dir)
        except Exception:
            # fall through to the recursive search before giving up
            pass

    # Tier 2 — recursive search (handles legacy nested orchestration layouts)
    found = _search_runs_dir(store.runs_dir, folder_id)
    if found:
        return found

    raise FileNotFoundError(
        f"No artifact zip found for folder id '{folder_id}' under {store.runs_dir}"
    )


def _search_runs_dir(runs_dir: Path, folder_id: str) -> Path | None:
    if not runs_dir.exists():
        return None

    candidates: list[Path] = []

    # Direct artifact-name match anywhere in the tree.
    candidates.extend(runs_dir.rglob(f"vectorforge_artifact_*{folder_id}*.zip"))
    candidates.extend(runs_dir.rglob(f"*{folder_id}*/artifact/*.zip"))

    # Any artifact zip living under a run dir whose path contains the folder id.
    for zip_path in runs_dir.rglob("artifact/*.zip"):
        if folder_id in str(zip_path):
            candidates.append(zip_path)

    if not candidates:
        return None

    # Newest by mtime wins (dedupe first).
    unique = {p.resolve(): p for p in candidates if p.is_file()}
    return max(unique.values(), key=lambda p: p.stat().st_mtime, default=None)
