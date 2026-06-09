from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vectorforge_v1.artifact_forge.contract import ArtifactGenerator


def get_artifact_generator(engine_type: str) -> "ArtifactGenerator":
    if engine_type == "autogluon_tabular":
        from vectorforge_v1.artifact_forge.generators.autogluon import AutoGluonArtifactGenerator
        return AutoGluonArtifactGenerator()
    if engine_type == "autorag":
        from vectorforge_v1.artifact_forge.generators.autorag import AutoRagArtifactGenerator
        return AutoRagArtifactGenerator()
    raise ValueError(f"unknown engine_type {engine_type!r}; supported: autogluon_tabular, autorag")
