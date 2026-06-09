from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TaskType = Literal["binary_classification", "multiclass_classification", "regression"]
Intent = Literal[
    "fast_baseline",
    "quality_search",
    "balanced_ensemble",
    "deployable_simple",
    "imbalance_aware",
    "threshold_tuning",
    "regression_quality",
    "multiclass_quality",
]
ModelFamily = Literal["GBM", "CAT", "XGB", "RF", "XT", "KNN", "LR", "NN_TORCH", "FASTAI"]


class MetricCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    reason: str


class PlannerDecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    metric_candidates: list[MetricCandidate]
    selected_primary_metric: str
    secondary_metrics: list[str]
    profile: str
    reasoning: str


class ExperimentConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presets: Literal["medium_quality", "good_quality", "high_quality"] = "medium_quality"
    time_limit: int = Field(default=300, ge=1, le=900)
    fit_weighted_ensemble: bool = True
    calibrate_decision_threshold: bool = False
    included_model_families: list[ModelFamily] = Field(default_factory=lambda: ["GBM", "RF"])
    infer_limit: float | None = None
    num_bag_folds: int | None = Field(default=None, ge=0)
    num_stack_levels: int | None = Field(default=None, ge=0)
    save_bag_folds: bool | None = None

    @model_validator(mode="after")
    def validate_bagging(self) -> "ExperimentConfigModel":
        if self.num_bag_folds == 1:
            raise ValueError("num_bag_folds must be 0 or at least 2")
        return self


class PlannedExperimentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    intent: Intent
    hypothesis: str
    config: ExperimentConfigModel


class RoundPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round: int
    round_goal: str
    experiments: list[PlannedExperimentModel]
