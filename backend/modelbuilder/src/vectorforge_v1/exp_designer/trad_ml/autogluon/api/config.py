from __future__ import annotations

from fastapi import APIRouter

from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config() -> dict:
    settings = get_settings()
    return {
        "planner_provider": settings.planner_provider,
        "ai_gateway_model": settings.ai_gateway_model,
        "ai_gateway_api_key_configured": bool(settings.ai_gateway_api_key),
        "openai_model": settings.openai_model,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "experiment_mode": settings.experiment_mode,
        "autogluon_fit_strategy": settings.autogluon_fit_strategy,
        "autogluon_num_cpus": settings.autogluon_num_cpus,
        "autogluon_num_gpus": settings.autogluon_num_gpus,
        "autogluon_num_bag_folds": settings.autogluon_num_bag_folds,
        "autogluon_num_stack_levels": settings.autogluon_num_stack_levels,
        "autogluon_save_bag_folds": settings.autogluon_save_bag_folds,
        "autogluon_refit_full": settings.autogluon_refit_full,
        "autogluon_verbosity": settings.autogluon_verbosity,
        "autogluon_max_auto_cpus_per_experiment": settings.autogluon_max_auto_cpus_per_experiment,
        "autogluon_fit_heartbeat_seconds": settings.autogluon_fit_heartbeat_seconds,
        "autogluon_small_data_fast_mode": settings.autogluon_small_data_fast_mode,
        "autogluon_small_data_max_rows": settings.autogluon_small_data_max_rows,
        "autogluon_disabled_model_families": settings.autogluon_disabled_model_families,
        "max_rounds": settings.max_rounds,
        "experiments_per_round": settings.experiments_per_round,
    }
