from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore


class CSVProfiler:
    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def profile(self, run_id: str, dataset_path: str, target_column: str) -> Path:
        dataframe = pd.read_csv(dataset_path)
        if target_column not in dataframe.columns:
            raise ValueError(f"Target column '{target_column}' was not found in the dataset")

        target = dataframe[target_column]
        features = dataframe.drop(columns=[target_column])
        profile: dict[str, Any] = {
            "dataset": {
                "rows": int(len(dataframe)),
                "columns": int(len(dataframe.columns)),
                "missing_cells_ratio": float(dataframe.isna().sum().sum() / max(dataframe.size, 1)),
            },
            "target": self._target_profile(target_column, target),
            "features": self._feature_profile(features),
        }
        path = self.artifact_store.run_dir(run_id) / "input" / "dataset_profile.json"
        return self.artifact_store.write_json(path, profile)

    def _target_profile(self, target_column: str, target: pd.Series) -> dict[str, Any]:
        non_missing = target.dropna()
        value_counts = non_missing.value_counts(dropna=False).head(50)
        class_distribution = {str(key): int(value) for key, value in value_counts.items()}
        min_count = int(value_counts.min()) if len(value_counts) else 0
        max_count = int(value_counts.max()) if len(value_counts) else 0
        imbalance_ratio = float(max_count / min_count) if min_count else None
        return {
            "name": target_column,
            "dtype": str(target.dtype),
            "unique_count": int(target.nunique(dropna=True)),
            "missing_ratio": float(target.isna().mean()),
            "class_distribution": class_distribution,
            "imbalance_ratio": imbalance_ratio,
        }

    def _feature_profile(self, features: pd.DataFrame) -> dict[str, Any]:
        numeric_columns = features.select_dtypes(include=["number"]).columns
        datetime_columns = features.select_dtypes(include=["datetime", "datetimetz"]).columns
        categorical_count = len(features.columns) - len(numeric_columns) - len(datetime_columns)
        row_count = max(len(features), 1)
        return {
            "numeric_count": int(len(numeric_columns)),
            "categorical_count": int(categorical_count),
            "datetime_count": int(len(datetime_columns)),
            "high_cardinality_columns": [
                column for column in features.columns if features[column].nunique(dropna=True) > min(50, row_count * 0.5)
            ],
            "constant_columns": [column for column in features.columns if features[column].nunique(dropna=True) <= 1],
            "mostly_missing_columns": [column for column in features.columns if features[column].isna().mean() >= 0.8],
        }
