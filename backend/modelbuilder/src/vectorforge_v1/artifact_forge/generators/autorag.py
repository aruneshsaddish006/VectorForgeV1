from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vectorforge_v1.artifact_forge.contract import ArtifactManifest, ArtifactNarrative
from vectorforge_v1.artifact_forge.packager import (
    assemble,
    atomic_write_json,
    pin_requirements_autorag,
    render_readme,
    render_metrics_md,
    render_dockerfile,
    render_deploy_sh,
    render_server_rag,
    render_cloudformation_rag,
    seal_zip,
)

_USER_REQUEST_FILE = "user_request.json"


class AutoRagArtifactGenerator:
    engine_type = "autorag"

    def generate(
        self,
        *,
        run_id: str,
        winner: dict[str, Any],
        run_dir: Path,
        out_dir: Path,
        narrative: ArtifactNarrative,
    ) -> Path:
        winning_config_yaml_path = winner.get("winning_config_yaml_path")
        corpus_path = winner.get("corpus_path") or self._find_corpus(run_dir)

        if not winning_config_yaml_path or not Path(winning_config_yaml_path).exists():
            raise ValueError(f"winning_config_yaml_path not found: {winning_config_yaml_path!r}")
        if not corpus_path or not Path(corpus_path).exists():
            raise ValueError(f"corpus_path not found: {corpus_path!r}")

        rag_config_src = Path(winning_config_yaml_path)
        corpus_src = Path(corpus_path)

        manifest = ArtifactManifest(
            engine_type=self.engine_type,
            task="rag_optimization",
            primary_metric=winner.get("primary_metric", "unknown"),
            primary_metric_value=winner.get("best_score") or winner.get("primary_metric_value"),
            secondary_metrics=winner.get("secondary_metrics") or {},
            io_schema={
                "input": "list[str] queries | str",
                "output": "list[{answer, contexts}]",
            },
            input_schema=[],
            trained_at=datetime.now(timezone.utc).isoformat(),
            runtime={
                "requires": ["AutoRAG==0.3.22", "openai"],
                "python": "3.12",
            },
        )

        templates_dir = Path(__file__).parent.parent / "templates"
        infer_content = (templates_dir / "infer_autorag.py.tmpl").read_text(encoding="utf-8")
        train_content = (templates_dir / "train_autorag.py.tmpl").read_text(encoding="utf-8")
        model_interface_content = (templates_dir / "model_interface.py.tmpl").read_text(encoding="utf-8")

        requirements_txt = pin_requirements_autorag()

        manifest_dict = manifest.model_dump()
        manifest_dict["run_id"] = run_id
        manifest_dict["best_experiment_id"] = winner.get("best_experiment_id") or winner.get("experiment_id", "unknown")

        run_context = self._get_run_context(run_dir, winner)
        sample_input = self._get_sample_queries(run_dir)
        if not sample_input:
            sample_input = narrative.sample_input

        readme_content = render_readme(
            narrative,
            manifest,
            commands={
                "infer": "python infer.py --query 'What is covered in this document?'",
                "train": "python train.py --corpus new_corpus.parquet --qa qa_data.parquet",
                "serve": "OPENAI_API_KEY=... uvicorn server:app --host 0.0.0.0 --port 8080",
            },
            run_context=run_context,
        )
        metrics_content = render_metrics_md(manifest)
        server_content = render_server_rag()
        dockerfile_content = render_dockerfile()
        deploy_sh_content = render_deploy_sh(run_id)
        cloudformation_content = render_cloudformation_rag(run_id)

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
            "sample_input.json": json.dumps(sample_input, indent=2),
            "model/rag_config.yaml": rag_config_src,
            "model/corpus.parquet": corpus_src,
        })

        atomic_write_json(pkg_dir / "manifest.json", manifest_dict)

        return seal_zip(pkg_dir)

    def _get_sample_queries(self, run_dir: Path) -> list[str] | None:
        """Pull up to 3 real queries from the QA parquet if available."""
        qa_path = self._find_qa(run_dir)
        if not qa_path:
            return None
        try:
            import pandas as pd
            df = pd.read_parquet(qa_path, engine="pyarrow")
            col = next((c for c in ("query", "question", "queries") if c in df.columns), None)
            if not col:
                return None
            return df[col].dropna().head(3).tolist()
        except Exception:
            return None

    def _get_run_context(self, run_dir: Path, winner: dict[str, Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = {"winner": winner}
        self._load_json_into(ctx, "user_request", run_dir / "input" / _USER_REQUEST_FILE)
        self._load_json_into(ctx, "dataset_profile", run_dir / "input" / "dataset_profile.json")
        self._load_json_into(ctx, "metric_decision", run_dir / "planning" / "metric_decision.json")
        self._load_json_into(ctx, "final_recommendation", run_dir / "reports" / "final_recommendation.json")
        experiments = self._collect_experiments(run_dir)
        if experiments:
            ctx["all_experiments"] = experiments
        return ctx

    def _collect_experiments(self, run_dir: Path) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for metrics_file in sorted((run_dir / "experiments").rglob("metrics.json")):
            try:
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                data["_experiment_path"] = str(metrics_file.parent.relative_to(run_dir))
                results.append(data)
            except Exception:
                pass
        return results

    def _load_json_into(self, ctx: dict[str, Any], key: str, path: Path) -> None:
        if path.exists():
            try:
                ctx[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _find_corpus(self, run_dir: Path) -> str | None:
        for candidate in [
            run_dir / "corpus.parquet",
            run_dir / "chunk_project" / "0.parquet",
        ]:
            if candidate.exists():
                return str(candidate)
        return None

    def _find_qa(self, run_dir: Path) -> str | None:
        for candidate in [
            run_dir / "qa.parquet",
            run_dir / "input" / "qa.parquet",
        ]:
            if candidate.exists():
                return str(candidate)
        return None
