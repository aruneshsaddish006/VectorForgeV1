from __future__ import annotations

import os
import importlib.util
import shutil
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import ExperimentResult
from vectorforge_v1.utils.elasticache_pubsub import publish_experiment_result


FALLBACK_MODEL_FAMILIES = ["RF", "XT", "LR", "KNN"]
SMALL_DATA_MODEL_FAMILIES = ["RF", "XT", "LR"]
TOTAL_PHASES = 5
OPTIONAL_FAMILY_IMPORTS = {
    "GBM": "lightgbm",
    "CAT": "catboost",
    "XGB": "xgboost",
    "NN_TORCH": "torch",
    "FASTAI": "fastai",
}


class ExperimentRunner:
    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def run(
        self,
        run_id: str,
        session_id: str,
        round_number: int,
        experiment: dict[str, Any],
        dataset_path: str,
        target_column: str,
        task_type: str,
        primary_metric: str,
        experiments_per_round: int = 1,
    ) -> ExperimentResult:
        if get_settings().experiment_mode == "autogluon":
            return self._run_autogluon(
                run_id,
                session_id,
                round_number,
                experiment,
                dataset_path,
                target_column,
                task_type,
                primary_metric,
                experiments_per_round,
            )
        return self._run_mock(run_id, session_id, round_number, experiment, primary_metric)

    def _experiment_dir(self, run_id: str, round_number: int, experiment_id: str) -> Path:
        path = self.artifact_store.run_dir(run_id) / "experiments" / f"round_{round_number}" / experiment_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_mock(
        self,
        run_id: str,
        session_id: str,
        round_number: int,
        experiment: dict[str, Any],
        primary_metric: str,
    ) -> ExperimentResult:
        experiment_id = experiment["experiment_id"]
        output_dir = self._experiment_dir(run_id, round_number, experiment_id)
        config_path = self.artifact_store.write_json(output_dir / "config.json", experiment)
        score = round(0.65 + (round_number * 0.03) + (int(experiment_id[-1]) * 0.01), 4)
        metrics_payload = {
            "primary_metric": primary_metric,
            "primary_metric_value": score,
            "secondary_metrics": {"precision": score, "recall": score},
            "holdout_validation": {"mode": "mock"},
            "mode": "mock",
        }
        metrics_path = self.artifact_store.write_json(
            output_dir / "metrics.json",
            metrics_payload,
        )
        self._publish_result(session_id, run_id, round_number, experiment_id, config_path, metrics_path, experiment, metrics_payload)
        model_dir = output_dir / "model"
        model_dir.mkdir(exist_ok=True)
        self.artifact_store.write_text(output_dir / "logs.txt", "Mock experiment completed.\n")
        self.artifact_store.write_status(run_id, "running", {"current_round": round_number})
        self.artifact_store.write_json(output_dir / "status.json", {"status": "completed"})
        return {
            "round": round_number,
            "experiment_id": experiment_id,
            "status": "completed",
            "primary_metric": primary_metric,
            "primary_metric_value": score,
            "metrics_path": str(metrics_path),
            "config_path": str(config_path),
            "model_path": str(model_dir),
            "error_summary": None,
            "secondary_metrics": {"precision": score, "recall": score},
            "holdout_metrics_path": str(metrics_path),
            "model_manifest_path": None,
        }

    def _run_autogluon(
        self,
        run_id: str,
        session_id: str,
        round_number: int,
        experiment: dict[str, Any],
        dataset_path: str,
        target_column: str,
        task_type: str,
        primary_metric: str,
        experiments_per_round: int,
    ) -> ExperimentResult:
        from autogluon.tabular import TabularPredictor

        experiment_id = experiment["experiment_id"]
        output_dir = self._experiment_dir(run_id, round_number, experiment_id)
        config_path = self.artifact_store.write_json(output_dir / "config.json", experiment)
        log_path = output_dir / "logs.txt"
        started_monotonic = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        config = experiment.get("config", {})
        time_limit = int(config.get("time_limit", 300))
        settings = get_settings()
        self._write_experiment_status(
            output_dir,
            "running",
            started_at=started_at,
            phase="load_data",
            elapsed_seconds=0.0,
            estimated_remaining_seconds=time_limit,
            fit_strategy=settings.autogluon_fit_strategy,
            progress_completed=0,
            progress_total=TOTAL_PHASES,
        )
        try:
            with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
                progress = tqdm(
                    total=TOTAL_PHASES,
                    desc=experiment_id,
                    unit="phase",
                    file=log_file,
                    leave=True,
                    mininterval=0,
                    ascii=True,
                    disable=False,
                )
                try:
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="load_data",
                        completed=0,
                        estimated_remaining_seconds=time_limit,
                        fit_strategy=settings.autogluon_fit_strategy,
                    )
                    dataframe = pd.read_csv(dataset_path)
                    if target_column not in dataframe.columns:
                        raise ValueError(f"Target column '{target_column}' was not found")
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="split_holdout",
                        completed=1,
                        estimated_remaining_seconds=time_limit,
                        fit_strategy=settings.autogluon_fit_strategy,
                    )
                    train_data, holdout_data = self._split_train_holdout(dataframe, target_column, task_type)
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="prepare_fit",
                        completed=2,
                        estimated_remaining_seconds=time_limit,
                        fit_strategy=settings.autogluon_fit_strategy,
                    )

                    model_dir = output_dir / "model"
                    if model_dir.exists():
                        shutil.rmtree(model_dir)
                    requested_families = config.get("included_model_families", [])
                    available_families, skipped_families = self._available_model_families(
                        requested_families,
                        train_rows=len(train_data),
                        small_data_fast_mode=settings.autogluon_small_data_fast_mode,
                        small_data_max_rows=settings.autogluon_small_data_max_rows,
                        disabled_families=settings.autogluon_disabled_model_families,
                    )
                    hyperparameters = {family: {} for family in available_families} or None
                    problem_type = {
                        "binary_classification": "binary",
                        "multiclass_classification": "multiclass",
                        "regression": "regression",
                    }[task_type]
                    num_cpus = self._num_cpus(settings.autogluon_num_cpus, experiments_per_round)
                    self._configure_local_thread_limits(num_cpus)
                    num_bag_folds = self._setting_or_config(
                        settings.autogluon_num_bag_folds,
                        config,
                        "num_bag_folds",
                    )
                    num_stack_levels = self._setting_or_config(
                        settings.autogluon_num_stack_levels,
                        config,
                        "num_stack_levels",
                    )
                    save_bag_folds = settings.autogluon_save_bag_folds
                    if skipped_families:
                        self._log_line(
                            log_file,
                            "Skipping unavailable AutoGluon model families: "
                            + ", ".join(f"{family} requires {package}" for family, package in skipped_families.items()),
                        )
                        self._log_line(log_file, "Effective model families: " + ", ".join(available_families))
                    self._log_line(
                        log_file,
                        "VectorForge timer: "
                        f"fit_strategy={settings.autogluon_fit_strategy}, "
                        f"num_cpus={num_cpus}, num_gpus={settings.autogluon_num_gpus}, "
                        f"num_bag_folds={num_bag_folds}, num_stack_levels={num_stack_levels}, "
                        f"save_bag_folds={save_bag_folds}, refit_full={settings.autogluon_refit_full}, "
                        f"small_data_fast_mode={settings.autogluon_small_data_fast_mode}, "
                        f"time_limit={time_limit}s, started_at={started_at}",
                    )
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="fit",
                        completed=2,
                        estimated_remaining_seconds=time_limit,
                        fit_strategy=settings.autogluon_fit_strategy,
                        num_cpus=num_cpus,
                        num_gpus=settings.autogluon_num_gpus,
                        num_bag_folds=num_bag_folds,
                        num_stack_levels=num_stack_levels,
                    )
                    fit_kwargs = {
                        "presets": config.get("presets", "medium_quality"),
                        "time_limit": time_limit,
                        "hyperparameters": hyperparameters,
                        "fit_weighted_ensemble": config.get("fit_weighted_ensemble", True),
                        "calibrate_decision_threshold": config.get("calibrate_decision_threshold", "auto"),
                        "dynamic_stacking": False,
                        "fit_strategy": settings.autogluon_fit_strategy,
                        "num_cpus": num_cpus,
                        "num_gpus": settings.autogluon_num_gpus,
                        "infer_limit": config.get("infer_limit"),
                        "save_bag_folds": save_bag_folds,
                        "refit_full": settings.autogluon_refit_full,
                        "set_best_to_refit_full": settings.autogluon_refit_full,
                    }
                    if num_bag_folds is not None:
                        fit_kwargs["num_bag_folds"] = num_bag_folds
                    if num_stack_levels is not None:
                        fit_kwargs["num_stack_levels"] = num_stack_levels
                    heartbeat_stop = threading.Event()
                    heartbeat_thread = self._start_fit_heartbeat(
                        heartbeat_stop,
                        output_dir=output_dir,
                        log_path=log_path,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        time_limit=time_limit,
                        interval_seconds=settings.autogluon_fit_heartbeat_seconds,
                        fit_strategy=settings.autogluon_fit_strategy,
                        num_cpus=num_cpus,
                        num_gpus=settings.autogluon_num_gpus,
                        num_bag_folds=num_bag_folds,
                        num_stack_levels=num_stack_levels,
                        model_families=available_families,
                    )
                    try:
                        predictor = TabularPredictor(
                            label=target_column,
                            problem_type=problem_type,
                            eval_metric=primary_metric,
                            path=str(model_dir),
                            verbosity=settings.autogluon_verbosity,
                        ).fit(train_data, **fit_kwargs)
                    finally:
                        heartbeat_stop.set()
                        heartbeat_thread.join(timeout=1)
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="evaluate_holdout",
                        completed=3,
                        estimated_remaining_seconds=0,
                        fit_strategy=settings.autogluon_fit_strategy,
                        num_cpus=num_cpus,
                        num_gpus=settings.autogluon_num_gpus,
                        num_bag_folds=num_bag_folds,
                        num_stack_levels=num_stack_levels,
                    )
                    evaluation = predictor.evaluate(holdout_data, silent=True)
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="running",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="write_metrics",
                        completed=4,
                        estimated_remaining_seconds=0,
                        fit_strategy=settings.autogluon_fit_strategy,
                        num_cpus=num_cpus,
                        num_gpus=settings.autogluon_num_gpus,
                        num_bag_folds=num_bag_folds,
                        num_stack_levels=num_stack_levels,
                    )

                    score = evaluation.get(primary_metric)
                    if score is None and "score" in evaluation:
                        score = evaluation["score"]
                    secondary_metrics = {
                        key: None if value is None else float(value)
                        for key, value in evaluation.items()
                        if key != primary_metric and isinstance(value, int | float)
                    }
                    metrics_payload = {
                        "primary_metric": primary_metric,
                        "primary_metric_value": score,
                        "secondary_metrics": secondary_metrics,
                        "evaluation": evaluation,
                        "holdout_validation": {
                            "train_rows": int(len(train_data)),
                            "holdout_rows": int(len(holdout_data)),
                            "method": "train_test_split",
                        },
                        "timing": {
                            "started_at": started_at,
                            "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
                            "time_limit_seconds": time_limit,
                        },
                        "fit_strategy": settings.autogluon_fit_strategy,
                        "num_cpus": num_cpus,
                        "num_gpus": settings.autogluon_num_gpus,
                        "num_bag_folds": num_bag_folds,
                        "num_stack_levels": num_stack_levels,
                        "save_bag_folds": save_bag_folds,
                        "refit_full": settings.autogluon_refit_full,
                        "requested_model_families": requested_families,
                        "effective_model_families": available_families,
                        "skipped_model_families": skipped_families,
                        "small_data_fast_mode": settings.autogluon_small_data_fast_mode,
                    }
                    metrics_path = self.artifact_store.write_json(output_dir / "metrics.json", metrics_payload)
                    self._publish_result(
                        session_id,
                        run_id,
                        round_number,
                        experiment_id,
                        config_path,
                        metrics_path,
                        experiment,
                        metrics_payload,
                    )
                    self._log_progress(
                        log_file,
                        progress,
                        output_dir,
                        status="completed",
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        phase="completed",
                        completed=TOTAL_PHASES,
                        estimated_remaining_seconds=0,
                        fit_strategy=settings.autogluon_fit_strategy,
                        num_cpus=num_cpus,
                        num_gpus=settings.autogluon_num_gpus,
                        num_bag_folds=num_bag_folds,
                        num_stack_levels=num_stack_levels,
                    )
                except Exception:
                    self._log_line(log_file, traceback.format_exc())
                    raise
                finally:
                    progress.close()
            return {
                "round": round_number,
                "experiment_id": experiment_id,
                "status": "completed",
                "primary_metric": primary_metric,
                "primary_metric_value": None if score is None else float(score),
                "metrics_path": str(metrics_path),
                "config_path": str(config_path),
                "model_path": str(model_dir),
                "error_summary": None,
                "secondary_metrics": secondary_metrics,
                "holdout_metrics_path": str(metrics_path),
                "model_manifest_path": None,
            }
        except Exception as exc:
            self._write_experiment_status(
                output_dir,
                "failed",
                error=str(exc),
                started_at=started_at,
                phase="failed",
                elapsed_seconds=round(time.monotonic() - started_monotonic, 3),
                estimated_remaining_seconds=0,
                fit_strategy=settings.autogluon_fit_strategy,
                progress_completed=0,
                progress_total=TOTAL_PHASES,
            )
            metrics_payload = {
                "primary_metric": primary_metric,
                "primary_metric_value": None,
                "error_summary": str(exc),
            }
            metrics_path = self.artifact_store.write_json(output_dir / "metrics.json", metrics_payload)
            self._publish_result(session_id, run_id, round_number, experiment_id, config_path, metrics_path, experiment, metrics_payload)
            return {
                "round": round_number,
                "experiment_id": experiment_id,
                "status": "failed",
                "primary_metric": primary_metric,
                "primary_metric_value": None,
                "metrics_path": str(metrics_path),
                "config_path": str(config_path),
                "model_path": None,
                "error_summary": str(exc),
                "secondary_metrics": {},
                "holdout_metrics_path": str(metrics_path),
                "model_manifest_path": None,
            }

    def _publish_result(
        self,
        session_id: str,
        run_id: str,
        round_number: int,
        experiment_id: str,
        config_path: str | Path,
        metrics_path: str | Path,
        config: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        publish_experiment_result(
            session_id=session_id,
            designer="autogluon",
            run_id=run_id,
            round_number=round_number,
            experiment_id=experiment_id,
            config_path=config_path,
            metrics_path=metrics_path,
            config=config,
            metrics=metrics,
        )

    def _available_model_families(
        self,
        requested_families: list[str],
        train_rows: int | None = None,
        small_data_fast_mode: bool = False,
        small_data_max_rows: int = 1000,
        disabled_families: list[str] | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        requested = requested_families or FALLBACK_MODEL_FAMILIES
        disabled = {family.upper() for family in disabled_families or []}
        if small_data_fast_mode and train_rows is not None and train_rows <= small_data_max_rows:
            requested = [family for family in requested if family in SMALL_DATA_MODEL_FAMILIES]
            if not requested:
                requested = SMALL_DATA_MODEL_FAMILIES.copy()
        available = []
        skipped = {}
        for family in requested:
            if family.upper() in disabled:
                skipped[family] = "disabled by VectorForge config"
                continue
            required_package = OPTIONAL_FAMILY_IMPORTS.get(family)
            if required_package and importlib.util.find_spec(required_package) is None:
                skipped[family] = required_package
                continue
            available.append(family)
        if not available:
            available = FALLBACK_MODEL_FAMILIES.copy()
        return available, skipped

    def _num_cpus(self, configured_num_cpus: int | None, experiments_per_round: int) -> int:
        if configured_num_cpus is not None:
            return max(1, configured_num_cpus)
        settings = get_settings()
        fair_share = max(1, (os.cpu_count() or 1) // max(1, experiments_per_round))
        return max(1, min(fair_share, settings.autogluon_max_auto_cpus_per_experiment))

    def _configure_local_thread_limits(self, num_cpus: int) -> None:
        thread_count = str(max(1, num_cpus))
        for env_var in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            os.environ.setdefault(env_var, thread_count)

    def _setting_or_config(self, setting_value: Any, config: dict[str, Any], key: str) -> Any:
        if setting_value is not None:
            return setting_value
        return config.get(key)

    def _config_value(self, config: dict[str, Any], key: str, default: Any) -> Any:
        value = config.get(key)
        return default if value is None else value

    def _log_line(self, log_file, message: str) -> None:
        log_file.write(f"\n{message}\n")
        log_file.flush()

    def _append_log_line(self, log_path: Path, message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{message}\n")

    def _start_fit_heartbeat(
        self,
        stop: threading.Event,
        output_dir: Path,
        log_path: Path,
        started_at: str,
        started_monotonic: float,
        time_limit: int,
        interval_seconds: float,
        **extra: Any,
    ) -> threading.Thread:
        def heartbeat() -> None:
            while not stop.wait(max(1.0, interval_seconds)):
                elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
                remaining = max(0, round(time_limit - elapsed_seconds, 3))
                payload = {
                    "started_at": started_at,
                    "phase": "fit",
                    "fit_subphase": "inside_autogluon_fit",
                    "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": elapsed_seconds,
                    "fit_elapsed_seconds": elapsed_seconds,
                    "estimated_remaining_seconds": remaining,
                    "progress_completed": 2,
                    "progress_total": TOTAL_PHASES,
                    "progress_percent": round((2 / TOTAL_PHASES) * 100, 1),
                    "debug_hint": (
                        "If this heartbeat keeps updating without new AutoGluon model logs, the run is blocked "
                        "inside the current model fit, most often native library threading or resource contention."
                    ),
                    **extra,
                }
                self._write_experiment_status(output_dir, "running", **payload)
                self._append_log_line(
                    log_path,
                    f"VectorForge heartbeat: fit still running, elapsed={elapsed_seconds}s, remaining~{remaining}s",
                )

        thread = threading.Thread(target=heartbeat, name=f"vectorforge-fit-heartbeat-{output_dir.name}", daemon=True)
        thread.start()
        return thread

    def _log_progress(
        self,
        log_file,
        progress,
        output_dir: Path,
        status: str,
        started_at: str,
        started_monotonic: float,
        phase: str,
        completed: int,
        estimated_remaining_seconds: float,
        **extra: Any,
    ) -> None:
        progress.set_postfix_str(phase)
        if progress.n < completed:
            progress.update(completed - progress.n)
        progress.refresh()
        elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
        self._log_line(
            log_file,
            f"VectorForge phase: {phase} ({completed}/{TOTAL_PHASES}), "
            f"elapsed={elapsed_seconds}s, remaining~{estimated_remaining_seconds}s",
        )
        self._write_experiment_status(
            output_dir,
            status,
            started_at=started_at,
            phase=phase,
            elapsed_seconds=elapsed_seconds,
            estimated_remaining_seconds=estimated_remaining_seconds,
            progress_completed=completed,
            progress_total=TOTAL_PHASES,
            progress_percent=round((completed / TOTAL_PHASES) * 100, 1),
            **extra,
        )

    def _write_experiment_status(self, output_dir: Path, status: str, **extra: Any) -> Path:
        return self.artifact_store.write_json(output_dir / "status.json", {"status": status, **extra})

    def _split_train_holdout(
        self,
        dataframe: pd.DataFrame,
        target_column: str,
        task_type: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if len(dataframe) < 8:
            return dataframe, dataframe
        stratify = None
        if task_type in {"binary_classification", "multiclass_classification"}:
            target_counts = dataframe[target_column].value_counts(dropna=False)
            if len(target_counts) > 1 and target_counts.min() >= 2:
                stratify = dataframe[target_column]
        try:
            return train_test_split(
                dataframe,
                test_size=0.25,
                random_state=42,
                stratify=stratify,
            )
        except ValueError:
            return train_test_split(dataframe, test_size=0.25, random_state=42)
