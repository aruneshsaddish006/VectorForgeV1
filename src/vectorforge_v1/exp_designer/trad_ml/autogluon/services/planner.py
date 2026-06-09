from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings
from vectorforge_v1.exp_designer.trad_ml.autogluon.schemas.planner_outputs import PlannerDecisionModel, RoundPlanModel
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore


class Planner(Protocol):
    def plan_initial_metric_decision(self, run_id: str, user_request: dict[str, Any], profile_path: str) -> Path: ...

    def plan_round(
        self,
        run_id: str,
        round_number: int,
        planner_decision: dict[str, Any],
        experiments_per_round: int,
        max_rounds: int,
    ) -> Path: ...


def get_planner() -> Planner:
    if get_settings().planner_provider == "openai":
        return OpenAIPlanner()
    return MockPlanner()


class MockPlanner:
    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def plan_initial_metric_decision(self, run_id: str, user_request: dict[str, Any], profile_path: str) -> Path:
        profile = self.artifact_store.read_json(Path(profile_path))
        task_type = self._infer_task_type(profile)
        metrics = self._metric_candidates(task_type, user_request.get("business_kpi") or "")
        decision = {
            "task_type": task_type,
            "metric_candidates": metrics,
            "selected_primary_metric": metrics[0]["metric"],
            "secondary_metrics": [candidate["metric"] for candidate in metrics[1:3]],
            "profile": "balanced_quality",
            "reasoning": "Mock planner selected a conservative metric/profile from dataset target facts and KPI text.",
        }
        model = PlannerDecisionModel.model_validate(decision)
        path = self.artifact_store.run_dir(run_id) / "planning" / "metric_decision.json"
        return self.artifact_store.write_json(path, model.model_dump())

    def plan_round(
        self,
        run_id: str,
        round_number: int,
        planner_decision: dict[str, Any],
        experiments_per_round: int,
        max_rounds: int,
    ) -> Path:
        metric = planner_decision["selected_primary_metric"]
        templates = [
            {
                "intent": "fast_baseline",
                "hypothesis": f"A medium-quality tree baseline can establish a competitive {metric} benchmark.",
                "config": {
                    "presets": "medium_quality",
                    "time_limit": 300,
                    "fit_weighted_ensemble": True,
                    "calibrate_decision_threshold": False,
                    "included_model_families": ["GBM", "RF"],
                },
            },
            {
                "intent": "balanced_ensemble",
                "hypothesis": f"Adding a wider ensemble should improve {metric} on mixed tabular features.",
                "config": {
                    "presets": "good_quality",
                    "time_limit": 300,
                    "fit_weighted_ensemble": True,
                    "calibrate_decision_threshold": True,
                    "included_model_families": ["GBM", "CAT", "RF", "XT"],
                },
            },
            {
                "intent": "deployable_simple",
                "hypothesis": f"A smaller model family set may preserve {metric} while reducing deployment complexity.",
                "config": {
                    "presets": "medium_quality",
                    "time_limit": 300,
                    "fit_weighted_ensemble": False,
                    "calibrate_decision_threshold": True,
                    "included_model_families": ["GBM", "RF"],
                },
            },
            {
                "intent": "quality_search",
                "hypothesis": f"A broader high-quality search may improve {metric} if extra training time is useful.",
                "config": {
                    "presets": "high_quality",
                    "time_limit": 300,
                    "fit_weighted_ensemble": True,
                    "calibrate_decision_threshold": True,
                    "included_model_families": ["GBM", "CAT", "XGB", "RF", "XT"],
                },
            },
            {
                "intent": "imbalance_aware",
                "hypothesis": f"Threshold calibration can improve {metric} on imbalanced targets.",
                "config": {
                    "presets": "good_quality",
                    "time_limit": 300,
                    "fit_weighted_ensemble": True,
                    "calibrate_decision_threshold": True,
                    "included_model_families": ["GBM", "RF", "XT"],
                },
            },
        ]
        experiments = []
        for index in range(experiments_per_round):
            template = templates[index % len(templates)]
            experiments.append(
                {
                    **template,
                    "experiment_id": f"r{round_number}_exp{index + 1}",
                }
            )
        plan = {
            "round": round_number,
            "round_goal": f"Round {round_number} of {max_rounds}: explore AutoGluon configurations for {metric}.",
            "experiments": experiments,
        }
        model = RoundPlanModel.model_validate(plan)
        path = self.artifact_store.run_dir(run_id) / "planning" / f"round_{round_number}_plan.json"
        return self.artifact_store.write_json(path, model.model_dump())

    def _infer_task_type(self, profile: dict[str, Any]) -> str:
        target = profile["target"]
        dtype = target["dtype"]
        unique_count = target["unique_count"]
        if dtype.startswith(("int", "float")) and unique_count > 20:
            return "regression"
        if unique_count <= 2:
            return "binary_classification"
        return "multiclass_classification"

    def _metric_candidates(self, task_type: str, business_kpi: str) -> list[dict[str, str]]:
        kpi = business_kpi.lower()
        if task_type == "regression":
            return [
                {"metric": "root_mean_squared_error", "reason": "Penalizes larger prediction errors."},
                {"metric": "mean_absolute_error", "reason": "Keeps average absolute error interpretable."},
                {"metric": "r2", "reason": "Shows explained variance against a simple baseline."},
            ]
        if task_type == "multiclass_classification":
            return [
                {"metric": "accuracy", "reason": "Measures overall multiclass correctness."},
                {"metric": "f1_macro", "reason": "Balances performance across classes."},
                {"metric": "balanced_accuracy", "reason": "Reduces dominance by frequent classes."},
            ]
        if "recall" in kpi or "miss" in kpi or "churn" in kpi:
            primary = {"metric": "f1", "reason": "Balances capture rate and outreach efficiency."}
        else:
            primary = {"metric": "roc_auc", "reason": "Measures ranking quality across thresholds."}
        return [
            primary,
            {"metric": "precision", "reason": "Controls waste from false positives."},
            {"metric": "recall", "reason": "Controls missed positive cases."},
        ]


class OpenAIPlanner:
    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()
        self.model = get_settings().openai_model

    def plan_initial_metric_decision(self, run_id: str, user_request: dict[str, Any], profile_path: str) -> Path:
        profile = self.artifact_store.read_json(Path(profile_path))
        parsed = self._parse(
            PlannerDecisionModel,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the VectorForge V1 AutoML planner. Return only structured data. "
                        "Choose one supported task type and metric. The planner may choose configs only; "
                        "it cannot request raw data, install packages, or write code."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "user_request": {
                            "problem_statement": user_request.get("problem_statement"),
                            "business_kpi": user_request.get("business_kpi"),
                            "target_column": user_request.get("target_column"),
                        },
                        "dataset_profile": profile,
                        "constraints": {
                            "supported_task_types": [
                                "binary_classification",
                                "multiclass_classification",
                                "regression",
                            ],
                            "supported_metrics": {
                                "binary_classification": ["f1", "recall", "precision", "roc_auc", "accuracy"],
                                "multiclass_classification": ["accuracy", "f1_macro", "balanced_accuracy"],
                                "regression": ["root_mean_squared_error", "mean_absolute_error", "r2"],
                            },
                            "profiles": ["balanced_quality"],
                        },
                    }),
                },
            ],
        )
        path = self.artifact_store.run_dir(run_id) / "planning" / "metric_decision.json"
        model = PlannerDecisionModel.model_validate(parsed)
        return self.artifact_store.write_json(path, model.model_dump())

    def plan_round(
        self,
        run_id: str,
        round_number: int,
        planner_decision: dict[str, Any],
        experiments_per_round: int,
        max_rounds: int,
    ) -> Path:
        run_dir = self.artifact_store.run_dir(run_id)
        profile = self.artifact_store.read_json(run_dir / "input" / "dataset_profile.json")
        previous_results = []
        leaderboard_path = run_dir / "reports" / "leaderboard.csv"
        if leaderboard_path.exists():
            previous_results = leaderboard_path.read_text(encoding="utf-8").splitlines()

        parsed = self._parse(
            RoundPlanModel,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the VectorForge V1 AutoML round planner. "
                        "Use only the allowed intents and config fields. For datasets under 1000 rows, keep "
                        "time_limit between 30 and 300 seconds and prefer medium_quality or good_quality. "
                        "Use 300 to 900 seconds only for larger datasets or when prior rounds justify it."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "round": round_number,
                        "max_rounds": max_rounds,
                        "dataset_profile": profile,
                        "selected_objective": planner_decision,
                        "previous_results": previous_results,
                        "constraints": {
                            "experiments_per_round": experiments_per_round,
                            "instruction": f"Generate exactly {experiments_per_round} experiments.",
                            "allowed_intents": [
                                "fast_baseline",
                                "quality_search",
                                "balanced_ensemble",
                                "deployable_simple",
                                "imbalance_aware",
                                "threshold_tuning",
                                "regression_quality",
                                "multiclass_quality",
                            ],
                            "allowed_config_fields": [
                                "presets",
                                "time_limit",
                                "fit_weighted_ensemble",
                                "calibrate_decision_threshold",
                                "included_model_families",
                                "infer_limit",
                                "num_bag_folds",
                                "num_stack_levels",
                                "save_bag_folds",
                            ],
                            "allowed_model_families": ["GBM", "CAT", "XGB", "RF", "XT", "KNN", "LR", "NN_TORCH", "FASTAI"],
                        },
                    }),
                },
            ],
        )
        if len(parsed.experiments) != experiments_per_round:
            raise ValueError(
                f"OpenAI planner returned {len(parsed.experiments)} experiments; expected {experiments_per_round}"
            )
        path = self.artifact_store.run_dir(run_id) / "planning" / f"round_{round_number}_plan.json"
        model = RoundPlanModel.model_validate(parsed)
        return self.artifact_store.write_json(path, model.model_dump())

    def _parse(self, schema, messages: list[dict[str, Any]]):
        from openai import OpenAI

        settings = get_settings()
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        if not api_key:
            raise RuntimeError(
                "OpenAI planner is enabled but no API key is configured. "
                "Set VECTORFORGE_OPENAI_API_KEY, OPENAI_API_KEY, or OPENAI_KEY."
            )
        client = OpenAI(api_key=api_key)
        response = client.responses.parse(
            model=self.model,
            input=messages,
            text_format=schema,
        )
        return response.output_parsed
