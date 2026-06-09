from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vectorforge_v1.artifact_forge.contract import ArtifactManifest, ArtifactNarrative
from vectorforge_v1.artifact_forge.packager import (
    assemble,
    atomic_write_json,
    pin_requirements,
    render_readme,
    render_metrics_md,
    seal_zip,
    render_server,
    render_dockerfile,
    render_deploy_sh,
    render_cloudformation,
)


_TORCH_FAMILIES = {"NN_TORCH", "FASTAI"}


class AutoGluonArtifactGenerator:
    engine_type = "autogluon_tabular"

    def generate(
        self,
        *,
        run_id: str,
        winner: dict[str, Any],
        run_dir: Path,
        out_dir: Path,
        narrative: ArtifactNarrative,
    ) -> Path:
        model_path = winner.get("model_path")
        if not model_path or not Path(model_path).exists():
            raise ValueError(f"Winner model_path not found: {model_path!r}")

        model_src = Path(model_path)
        engine_families = self._get_engine_families(winner)
        input_schema = self._get_input_schema(run_dir)
        task = self._get_task(run_dir)

        manifest = ArtifactManifest(
            engine_type=self.engine_type,
            task=task,
            primary_metric=winner.get("primary_metric", "unknown"),
            primary_metric_value=winner.get("primary_metric_value"),
            secondary_metrics=winner.get("secondary_metrics") or {},
            io_schema={
                "input": "list[dict] | csv_path | DataFrame",
                "output": "list[prediction]",
            },
            input_schema=input_schema,
            trained_at=datetime.now(timezone.utc).isoformat(),
            runtime={
                "requires": ["autogluon-tabular"] + self._family_packages(engine_families),
                "python": "3.12",
            },
        )

        templates_dir = Path(__file__).parent.parent / "templates"
        infer_content = (templates_dir / "infer_autogluon.py.tmpl").read_text(encoding="utf-8")
        train_content = (templates_dir / "train_autogluon.py.tmpl").read_text(encoding="utf-8")
        model_interface_content = (templates_dir / "model_interface.py.tmpl").read_text(encoding="utf-8")

        requirements_txt = pin_requirements(engine_families)

        manifest_dict = manifest.model_dump()
        manifest_dict["run_id"] = run_id
        manifest_dict["experiment_id"] = winner.get("experiment_id", "unknown")

        # Derive sample input from real dataset rows (drop target column)
        sample_input = self._get_sample_input(run_dir)
        if not sample_input:
            sample_input = narrative.sample_input
        sample_input_json = json.dumps(sample_input, indent=2)

        task_type = manifest_dict.get("task", "tabular_ml")
        target_col = self._get_target_column(run_dir)
        run_context = self._get_run_context(run_dir, winner)

        server_content = render_server(task_type)
        dockerfile_content = render_dockerfile()
        deploy_sh_content = render_deploy_sh(run_id)
        cloudformation_content = render_cloudformation(run_id)
        readme_content = render_readme(
            narrative,
            manifest,
            commands={
                "infer": "python infer.py --input sample_input.json",
                "train": f"python train.py --dataset your_dataset.csv --target {target_col or '<target_col>'}",
            },
            engine_families=engine_families,
            run_context=run_context,
        )
        metrics_content = render_metrics_md(manifest)

        pkg_dir = out_dir
        pkg_dir.mkdir(parents=True, exist_ok=True)

        assemble(pkg_dir, {
            "infer.py": infer_content,
            "train.py": train_content,
            "model_interface.py": model_interface_content,
            "server.py": server_content,
            "Dockerfile": dockerfile_content,
            "deploy.sh": deploy_sh_content,
            "cloudformation.yaml": cloudformation_content,
            "requirements.txt": requirements_txt,
            "README.md": readme_content,
            "METRICS.md": metrics_content,
            "sample_input.json": sample_input_json,
            "model": model_src,
        })

        atomic_write_json(pkg_dir / "manifest.json", manifest_dict)

        return seal_zip(pkg_dir)

    def _get_sample_input(self, run_dir: Path) -> list[dict[str, Any]] | None:
        dataset_path = run_dir / "input" / "dataset.csv"
        if not dataset_path.exists():
            return None
        target_col = self._get_target_column(run_dir)
        try:
            import csv
            with dataset_path.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = [
                    self._coerce_row(row, target_col)
                    for i, row in enumerate(reader)
                    if i < 2
                ]
            return rows if rows else None
        except Exception:
            return None

    def _coerce_row(self, row: dict[str, str], target_col: str | None) -> dict[str, Any]:
        record: dict[str, Any] = {}
        for k, v in row.items():
            if target_col and k == target_col:
                continue
            record[k] = self._coerce_value(v)
        return record

    def _coerce_value(self, v: str) -> Any:
        try:
            return int(v)
        except (ValueError, TypeError):
            pass
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
        return v

    _USER_REQUEST_FILE = "user_request.json"

    def _get_target_column(self, run_dir: Path) -> str | None:
        request_path = run_dir / "input" / self._USER_REQUEST_FILE
        if request_path.exists():
            try:
                return json.loads(request_path.read_text(encoding="utf-8")).get("target_column")
            except Exception:
                pass
        return None

    def _get_run_context(self, run_dir: Path, winner: dict[str, Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = {"winner": winner}
        self._load_json_into(ctx, "user_request", run_dir / "input" / self._USER_REQUEST_FILE)
        self._load_json_into(ctx, "dataset_profile", run_dir / "input" / "dataset_profile.json")
        self._load_json_into(ctx, "metric_decision", run_dir / "planning" / "metric_decision.json")
        self._load_json_into(ctx, "final_recommendation", run_dir / "reports" / "final_recommendation.json")
        experiments: list[dict[str, Any]] = []
        for metrics_file in sorted((run_dir / "experiments").rglob("metrics.json")):
            try:
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                data["_experiment_path"] = str(metrics_file.parent.relative_to(run_dir))
                experiments.append(data)
            except Exception:
                pass
        if experiments:
            ctx["all_experiments"] = experiments
        return ctx

    def _load_json_into(self, ctx: dict[str, Any], key: str, path: Path) -> None:
        if path.exists():
            try:
                ctx[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _get_engine_families(self, winner: dict[str, Any]) -> list[str]:
        metrics_path = winner.get("metrics_path") or winner.get("holdout_metrics_path")
        families = self._families_from_metrics(metrics_path)
        if families:
            return families
        families = self._families_from_config(winner.get("config_path"))
        return families or ["GBM", "RF"]

    def _families_from_metrics(self, metrics_path: str | None) -> list[str]:
        if not metrics_path:
            return []
        mp = Path(metrics_path)
        if not mp.exists():
            return []
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
            families = data.get("effective_model_families") or data.get("model_families")
            return list(families) if families else []
        except Exception:
            return []

    def _families_from_config(self, config_path: str | None) -> list[str]:
        if not config_path:
            return []
        cp = Path(config_path)
        if not cp.exists():
            return []
        try:
            data = json.loads(cp.read_text(encoding="utf-8"))
            families = data.get("config", data).get("included_model_families")
            return list(families) if families else []
        except Exception:
            return []

    def _get_input_schema(self, run_dir: Path) -> list[dict[str, Any]]:
        profile_path = run_dir / "input" / "dataset_profile.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                columns = profile.get("columns") or profile.get("features") or []
                return [
                    {"name": c.get("name", c.get("column", "")), "dtype": c.get("dtype", "object")}
                    for c in columns
                    if c.get("name") or c.get("column")
                ]
            except Exception:
                pass
        return []

    def _get_task(self, run_dir: Path) -> str:
        decision_path = run_dir / "planning" / "metric_decision.json"
        if decision_path.exists():
            try:
                data = json.loads(decision_path.read_text(encoding="utf-8"))
                return data.get("task_type", "tabular_ml")
            except Exception:
                pass
        return "tabular_ml"

    def _family_packages(self, families: list[str]) -> list[str]:
        pkg_map = {
            "GBM": "lightgbm",
            "CAT": "catboost",
            "XGB": "xgboost",
            "NN_TORCH": "torch",
            "FASTAI": "fastai",
        }
        pkgs = []
        for f in families:
            pkg = pkg_map.get(f.upper())
            if pkg:
                pkgs.append(pkg)
        return pkgs
