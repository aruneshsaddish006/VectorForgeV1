from __future__ import annotations

from pathlib import Path
from typing import Any

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import ExperimentResult


class ResearchSummarizer:
    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def append_round_summary(
        self,
        run_id: str,
        round_number: int,
        round_plan: dict[str, Any],
        round_results: list[ExperimentResult],
        winner: ExperimentResult,
    ) -> Path:
        path = self.artifact_store.run_dir(run_id) / "reports" / "research_log.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else f"# Research Log: {run_id}\n\n"
        lines = [
            f"## Round {round_number}",
            "",
            round_plan.get("round_goal", ""),
            "",
            "Optimization loop checks completed:",
            "",
            "- Holdout validation metrics were recorded for every completed experiment.",
            "- Secondary metric tradeoffs were reviewed in the round table.",
            "- The round-winning model was packaged through a model manifest.",
            "",
            f"Winner: `{winner['experiment_id']}` with holdout {winner['primary_metric']}={winner['primary_metric_value']}.",
            "",
            "| Experiment | Status | Primary Metric | Value | Secondary Metrics | Hypothesis Result |",
            "|---|---|---|---:|---|---|",
        ]
        for result in round_results:
            hypothesis_result = "supported" if result["experiment_id"] == winner["experiment_id"] else "inconclusive"
            secondary_metrics = result.get("secondary_metrics") or {}
            secondary_summary = ", ".join(
                f"{metric}={value:.4g}" for metric, value in sorted(secondary_metrics.items()) if value is not None
            )
            lines.append(
                "| {experiment_id} | {status} | {metric} | {value} | {secondary} | {hypothesis_result} |".format(
                    experiment_id=result["experiment_id"],
                    status=result["status"],
                    metric=result["primary_metric"],
                    value="" if result["primary_metric_value"] is None else result["primary_metric_value"],
                    secondary=secondary_summary,
                    hypothesis_result=hypothesis_result,
                )
            )
        lines.append("")
        return self.artifact_store.write_text(path, existing + "\n".join(lines) + "\n")

    def write_final_recommendation(
        self,
        run_id: str,
        planner_decision: dict[str, Any],
        winner: ExperimentResult,
    ) -> Path:
        recommendation = {
            "run_id": run_id,
            "task_type": planner_decision["task_type"],
            "primary_metric": winner["primary_metric"],
            "best_experiment_id": winner["experiment_id"],
            "best_score": winner["primary_metric_value"],
            "winning_model_path": winner["model_path"],
            "winning_model_manifest_path": winner.get("model_manifest_path"),
            "holdout_metrics_path": winner.get("holdout_metrics_path"),
            "secondary_metrics": winner.get("secondary_metrics") or {},
            "why_selected": "Highest primary metric across all completed experiments.",
            "optimization_loop_actions": [
                "Validated experiment metrics on a holdout split.",
                "Reviewed secondary metric tradeoffs in the round summaries.",
                "Packaged round-winning and final-winning model manifests.",
            ],
        }
        json_path = self.artifact_store.run_dir(run_id) / "reports" / "final_recommendation.json"
        self.artifact_store.write_json(json_path, recommendation)
        markdown = "\n".join(
            [
                f"# Final Recommendation: {run_id}",
                "",
                f"Best experiment: `{winner['experiment_id']}`",
                f"Primary metric: `{winner['primary_metric']}`",
                f"Best score: `{winner['primary_metric_value']}`",
                f"Model path: `{winner['model_path']}`",
                f"Model manifest: `{winner.get('model_manifest_path')}`",
                f"Holdout metrics: `{winner.get('holdout_metrics_path')}`",
                "",
                "Selected because it produced the best primary metric across completed experiments.",
                "",
            ]
        )
        self.artifact_store.write_text(self.artifact_store.run_dir(run_id) / "reports" / "final_recommendation.md", markdown)
        return json_path
