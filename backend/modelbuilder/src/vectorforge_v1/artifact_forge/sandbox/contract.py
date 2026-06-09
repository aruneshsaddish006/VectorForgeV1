from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from vectorforge_v1.artifact_forge.contract import SmokeResult


@runtime_checkable
class SmokeRunner(Protocol):
    def run(
        self,
        package_dir: Path,
        depth: Literal["full", "contract"] = "full",
    ) -> SmokeResult: ...


def get_smoke_runner() -> SmokeRunner:
    from vectorforge_v1.artifact_forge.config import get_settings
    backend = get_settings().smoke_backend
    if backend == "opensandbox":
        from vectorforge_v1.artifact_forge.sandbox.opensandbox_runner import OpenSandboxRunner
        return OpenSandboxRunner()
    if backend == "vercel":
        from vectorforge_v1.artifact_forge.sandbox.vercel_runner import VercelSandboxRunner
        return VercelSandboxRunner()
    if backend == "local":
        from vectorforge_v1.artifact_forge.sandbox.local_runner import LocalSubprocessRunner
        return LocalSubprocessRunner()
    raise ValueError(f"Unknown smoke_backend: {backend!r}")
