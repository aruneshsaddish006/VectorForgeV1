"""
DockerDeployRunner — build the Docker image from a sealed artifact zip and,
when AWS credentials are supplied, execute the artifact's deploy.sh.

deploy.sh (rendered by packager.render_deploy_sh) builds + pushes to ECR and
deploys a CloudFormation App Runner stack. It needs, in the subprocess env:

    AWS_ACCOUNT_ID, AWS_REGION                        (consumed by deploy.sh)
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,         (consumed by the aws CLI)
    AWS_SESSION_TOKEN (optional, for STS/assumed-role)

Credentials are injected into the subprocess environment only — never written
to disk, never echoed into the result, and scrubbed from the captured log tail.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


class DeployError(Exception):
    """Fatal deploy error — aborts the run (docker/zip/workspace problems)."""


DeployStatus = Literal["built", "deployed", "skipped", "failed", "running"]

# Patterns scrubbed from any captured log line.
_AWS_ACCOUNT_RE = re.compile(r"\b\d{12}\b")
_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")


@dataclass
class DeployResult:
    status: DeployStatus
    run_id: str
    app_name: str
    image_tag: str | None = None
    image_built: bool = False
    deploy_ran: bool = False
    ecr_uri: str | None = None
    stack_name: str | None = None
    service_url: str | None = None
    workspace_dir: str | None = None
    docker_exit_code: int | None = None
    deploy_exit_code: int | None = None
    error: str | None = None
    log_tail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class DockerDeployRunner:
    def __init__(
        self,
        *,
        run_id: str,
        run_dir: Path,
        allow_deploy: bool = True,
        workspace_root: Path | None = None,
        docker_bin: str = "docker",
        build_timeout: int = 1800,
        deploy_timeout: int = 1800,
        force_rebuild: bool = False,
        log_tail_size: int = 200,
    ) -> None:
        self.run_id = run_id
        self.run_dir = Path(run_dir)
        self.allow_deploy = allow_deploy
        self.workspace_root = workspace_root or (self.run_dir / "deploy_workspace")
        self.docker_bin = docker_bin
        self.build_timeout = build_timeout
        self.deploy_timeout = deploy_timeout
        self.force_rebuild = force_rebuild
        self.log_tail_size = log_tail_size
        # MUST match packager.render_deploy_sh's APP_NAME.
        self.app_name = run_id.replace("_", "-").lower()
        self._tail: list[str] = []

    # ── public API ────────────────────────────────────────────────────────────

    def run(
        self,
        zip_path: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> DeployResult:
        env_overrides = env_overrides or {}
        result = DeployResult(
            status="failed",
            run_id=self.run_id,
            app_name=self.app_name,
            stack_name=f"vf-{self.app_name}",
        )
        try:
            self._check_docker_available()
            zip_path = self._resolve_zip(zip_path)
            work_dir = self._unpack(zip_path)
            result.workspace_dir = str(work_dir)

            image_ref = f"{self.app_name}:latest"
            result.image_tag = image_ref
            built, code = self._docker_build(work_dir, image_ref)
            result.image_built = built
            result.docker_exit_code = code
            if code != 0:
                result.status = "failed"
                result.error = f"docker build failed (exit {code})"
                result.log_tail = list(self._tail)
                return result

            merged_env = self._build_env(env_overrides)
            if not self._should_deploy(merged_env):
                result.status = "built"
                result.log_tail = list(self._tail)
                return result

            d_code = self._run_deploy_sh(work_dir, merged_env)
            result.deploy_ran = True
            result.deploy_exit_code = d_code
            self._parse_deploy_outputs(result)
            if d_code == 0:
                result.status = "deployed"
            else:
                result.status = "failed"
                result.error = f"deploy.sh failed (exit {d_code})"
            result.log_tail = list(self._tail)
            return result

        except DeployError as exc:
            result.status = "failed"
            result.error = str(exc)
            result.log_tail = list(self._tail)
            return result
        except Exception as exc:  # noqa: BLE001 — runner is total; never raises
            result.status = "failed"
            result.error = f"unexpected: {exc!s}"
            result.log_tail = list(self._tail)
            return result

    # ── gating ────────────────────────────────────────────────────────────────

    def _should_deploy(self, env: dict[str, str]) -> bool:
        return (
            self.allow_deploy
            and bool(env.get("AWS_ACCOUNT_ID"))
            and bool(env.get("AWS_ACCESS_KEY_ID"))
            and bool(env.get("AWS_SECRET_ACCESS_KEY"))
        )

    def _build_env(self, env_overrides: dict[str, str]) -> dict[str, str]:
        env = dict(os.environ)
        env.update(env_overrides)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    # ── docker availability ───────────────────────────────────────────────────

    def _check_docker_available(self) -> None:
        if shutil.which(self.docker_bin) is None:
            raise DeployError("docker binary not found on PATH")
        try:
            proc = subprocess.run(
                [self.docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            raise DeployError(f"docker daemon check failed: {exc!s}") from exc
        if proc.returncode != 0:
            raise DeployError("docker daemon not reachable")

    # ── zip resolution + unpack ───────────────────────────────────────────────

    def _resolve_zip(self, zip_path: Path | None) -> Path:
        if zip_path and Path(zip_path).exists():
            return Path(zip_path)
        try:
            from vectorforge_v1.artifact_forge.artifact_resolver import (
                ensure_artifact_zip_for_run,
                find_artifact_zip_in_run_dir,
            )
            found = find_artifact_zip_in_run_dir(self.run_dir)
            if found:
                return found
            return ensure_artifact_zip_for_run(run_id=self.run_id, run_dir=self.run_dir)
        except Exception as exc:  # noqa: BLE001
            raise DeployError(f"could not resolve artifact zip: {exc!s}") from exc

    def _unpack(self, zip_path: Path) -> Path:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        inner = self.workspace_root / f"vectorforge_artifact_{self.run_id}"
        if inner.exists():
            shutil.rmtree(inner)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(self.workspace_root)
        except zipfile.BadZipFile as exc:
            raise DeployError(f"corrupt artifact zip: {zip_path}") from exc

        # The zip nests vectorforge_artifact_{run_id}/... — but be tolerant of a
        # differently-named top-level dir by locating the Dockerfile if needed.
        if not (inner / "Dockerfile").exists():
            inner = self._find_artifact_root(self.workspace_root)
        if inner is None or not (inner / "Dockerfile").exists():
            raise DeployError("Dockerfile not found in unpacked artifact")
        if not (inner / "deploy.sh").exists():
            raise DeployError("deploy.sh not found in unpacked artifact")
        return inner

    @staticmethod
    def _find_artifact_root(root: Path) -> Path | None:
        for dockerfile in root.rglob("Dockerfile"):
            if (dockerfile.parent / "deploy.sh").exists():
                return dockerfile.parent
        return None

    # ── docker build (idempotent) ─────────────────────────────────────────────

    def _image_exists(self, image_ref: str) -> bool:
        proc = subprocess.run(
            [self.docker_bin, "image", "inspect", image_ref],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0

    def _docker_build(self, work_dir: Path, image_ref: str) -> tuple[bool, int]:
        if not self.force_rebuild and self._image_exists(image_ref):
            self._emit(f"[vectorforge] image {image_ref} already exists — skipping build\n")
            return (False, 0)
        code = self._stream_subprocess(
            [self.docker_bin, "build", "-t", image_ref, "."],
            cwd=work_dir, env=None, timeout=self.build_timeout,
        )
        return (True, code)

    # ── deploy.sh ─────────────────────────────────────────────────────────────

    def _run_deploy_sh(self, work_dir: Path, env: dict[str, str]) -> int:
        return self._stream_subprocess(
            ["bash", "deploy.sh"], cwd=work_dir, env=env, timeout=self.deploy_timeout,
        )

    def _parse_deploy_outputs(self, result: DeployResult) -> None:
        ecr_re = re.compile(r"\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/\S+:\S+")
        url_re = re.compile(r"https://\S+\.awsapprunner\.com\S*")
        for line in self._tail:
            m = ecr_re.search(line)
            if m:
                result.ecr_uri = m.group(0)
            u = url_re.search(line)
            if u:
                result.service_url = u.group(0)

    # ── subprocess streaming (internal — correct long-process handling) ───────

    def _emit(self, line: str) -> None:
        scrubbed = _AWS_ACCESS_KEY_RE.sub("***", _AWS_ACCOUNT_RE.sub("************", line)).rstrip("\n")
        self._tail.append(scrubbed)
        if len(self._tail) > self.log_tail_size:
            del self._tail[: len(self._tail) - self.log_tail_size]

    def _stream_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        env: dict[str, str] | None,
        timeout: int,
    ) -> int:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        try:
            assert proc.stdout is not None
            for line in iter(proc.stdout.readline, ""):
                self._emit(line)
            proc.stdout.close()
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self._emit(f"[vectorforge] command timed out after {timeout}s\n")
            return 124
        finally:
            if proc.poll() is None:
                proc.kill()
