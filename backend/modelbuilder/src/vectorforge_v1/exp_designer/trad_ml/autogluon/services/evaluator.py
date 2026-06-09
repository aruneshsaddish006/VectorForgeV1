from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import ExperimentResult


LOWER_IS_BETTER = {"root_mean_squared_error", "mean_absolute_error"}


class ResultEvaluator:
    def select_winner(self, results: list[ExperimentResult], primary_metric: str) -> ExperimentResult:
        successful = [
            result
            for result in results
            if result["status"] == "completed" and result["primary_metric_value"] is not None
        ]
        if not successful:
            raise ValueError("No successful experiment results were available for winner selection")
        reverse = primary_metric not in LOWER_IS_BETTER
        return sorted(successful, key=lambda result: result["primary_metric_value"] or 0.0, reverse=reverse)[0]
