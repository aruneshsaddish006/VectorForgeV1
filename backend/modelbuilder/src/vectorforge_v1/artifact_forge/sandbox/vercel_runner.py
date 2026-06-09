from __future__ import annotations

from pathlib import Path
from typing import Literal

from vectorforge_v1.artifact_forge.contract import SmokeResult


class VercelSandboxRunner:
    def run(
        self,
        package_dir: Path,
        depth: Literal["full", "contract"] = "full",
    ) -> SmokeResult:
        raise NotImplementedError(
            "vercel sandbox backend not yet wired — TODO qualification gate"
        )
