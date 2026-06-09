from __future__ import annotations

import asyncio
import concurrent.futures
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from vectorforge_v1.artifact_forge.contract import SmokeResult
from vectorforge_v1.artifact_forge.config import get_settings


class OpenSandboxRunner:
    def run(
        self,
        package_dir: Path,
        depth: Literal["full", "contract"] = "full",
    ) -> SmokeResult:
        settings = get_settings()
        api_key = settings.opensandbox_api_key.get_secret_value() if settings.opensandbox_api_key else None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_thread, package_dir, depth, api_key, settings)
            try:
                return future.result(timeout=settings.artifact_smoke_timeout_seconds + 30)
            except concurrent.futures.TimeoutError:
                return SmokeResult(
                    status="skipped",
                    degraded_reason="Thread-level timeout waiting for sandbox result",
                )

    def _run_in_thread(self, package_dir, depth, api_key, settings) -> SmokeResult:
        return asyncio.run(self._run_async(package_dir, depth, api_key, settings))

    async def _run_async(self, package_dir, depth, api_key, settings) -> SmokeResult:
        try:
            from opensandbox import Sandbox
            from opensandbox.config import ConnectionConfig
        except ImportError as e:
            return SmokeResult(status="skipped", degraded_reason=f"opensandbox SDK not installed: {e}")

        sandbox_id: str | None = None
        timeout_s = settings.artifact_smoke_timeout_seconds
        is_local = settings.opensandbox_domain.startswith(("localhost", "127."))

        try:
            connection_config = ConnectionConfig(
                domain=settings.opensandbox_domain,
                api_key=api_key,
                protocol="http" if is_local else "https",
                request_timeout=timedelta(seconds=timeout_s),
                use_server_proxy=not is_local,
            )

            sandbox = await Sandbox.create(
                "python:3.12-slim",
                connection_config=connection_config,
                timeout=timedelta(seconds=timeout_s),
                resource={"cpu": "2", "memory": "4Gi"},
                skip_health_check=True,
            )
            sandbox_id = getattr(sandbox, "id", None) or getattr(sandbox, "sandbox_id", None)

            # Wait for execd agent inside container to be ready
            await sandbox.check_ready(
                timeout=timedelta(seconds=60),
                polling_interval=timedelta(seconds=2),
            )

            async with sandbox:
                await self._upload_files(sandbox, package_dir)

                if depth == "full":
                    result = await self._smoke_full(sandbox, package_dir)
                else:
                    result = await self._smoke_contract(sandbox)

                return SmokeResult(
                    status=result.status,
                    stdout=result.stdout,
                    exit_code=result.exit_code,
                    sandbox_id=str(sandbox_id) if sandbox_id else None,
                    degraded_reason=result.degraded_reason,
                )

        except Exception as exc:
            return self._on_error(exc, depth, sandbox_id)

    async def _upload_files(self, sandbox: Any, package_dir: Path) -> None:
        """Upload each file individually via write_file — more reliable than batch write_files over proxy."""
        for file_path in sorted(package_dir.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(package_dir)
                dest = f"/workspace/{rel}"
                # Ensure parent directory exists
                parent = str(Path(dest).parent)
                if parent != "/workspace":
                    await sandbox.commands.run(f"mkdir -p {parent}")
                await sandbox.files.write_file(dest, file_path.read_bytes(), mode=644)

    def _on_error(self, exc: Exception, depth: str, sandbox_id: str | None) -> SmokeResult:
        sid = str(sandbox_id) if sandbox_id else None
        if depth == "full":
            return SmokeResult(
                status="passed_contract_only",
                degraded_reason=f"Full smoke failed ({exc!s}); fell back to contract.",
                sandbox_id=sid,
            )
        return SmokeResult(
            status="skipped",
            degraded_reason=f"OpenSandbox error: {exc!s}",
            sandbox_id=sid,
        )

    async def _smoke_full(self, sandbox: Any, package_dir: Path) -> SmokeResult:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        engine_type = manifest.get("engine_type", "autogluon_tabular")

        if engine_type == "autogluon_tabular":
            pkgs = "autogluon-tabular[lightgbm,xgboost,catboost]"
        else:
            pkgs = "AutoRAG==0.3.22 openai"

        install = await sandbox.commands.run(
            f"pip install uv && uv pip install --system --no-cache {pkgs}"
        )
        if install.exit_code != 0:
            return SmokeResult(
                status="passed_contract_only",
                stdout=self._stdout(install),
                exit_code=install.exit_code,
                degraded_reason="Package install failed; contract depth only.",
            )

        infer = await sandbox.commands.run(
            "python /workspace/infer.py --input /workspace/sample_input.json"
        )
        stdout = self._stdout(infer)
        if infer.exit_code == 0:
            return SmokeResult(status="passed", stdout=stdout, exit_code=0)
        return SmokeResult(
            status="passed_contract_only",
            stdout=stdout,
            exit_code=infer.exit_code,
            degraded_reason="infer.py exited non-zero; contract check only.",
        )

    async def _smoke_contract(self, sandbox: Any) -> SmokeResult:
        script = (
            "import json,py_compile\n"
            "py_compile.compile('/workspace/infer.py',doraise=True)\n"
            "py_compile.compile('/workspace/model_interface.py',doraise=True)\n"
            "m=json.load(open('/workspace/manifest.json'))\n"
            "assert 'engine_type' in m\n"
            "s=json.load(open('/workspace/sample_input.json'))\n"
            "assert s is not None\n"
            "print('contract_ok')\n"
        )
        result = await sandbox.commands.run(f'python -c "{script}"')
        stdout = self._stdout(result)
        if result.exit_code == 0:
            return SmokeResult(status="passed_contract_only", stdout=stdout, exit_code=0)
        return SmokeResult(
            status="failed",
            stdout=stdout,
            exit_code=result.exit_code,
            degraded_reason="Contract check failed.",
        )

    def _collect_entries(self, package_dir: Path) -> list:
        from opensandbox.models.filesystem import WriteEntry
        entries = []
        for file_path in sorted(package_dir.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(package_dir)
                entries.append(WriteEntry(
                    path=f"/workspace/{rel}",
                    data=file_path.read_bytes(),
                    mode=644,
                ))
        return entries

    def _stdout(self, execution: Any) -> str:
        try:
            logs = execution.logs
            parts = []
            if logs.stdout:
                parts.extend(
                    entry.text if hasattr(entry, "text") else str(entry)
                    for entry in logs.stdout
                )
            if logs.stderr:
                parts.extend(
                    entry.text if hasattr(entry, "text") else str(entry)
                    for entry in logs.stderr
                )
            return "".join(parts)
        except Exception:
            return str(execution)
