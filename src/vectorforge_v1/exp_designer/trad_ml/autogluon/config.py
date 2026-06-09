from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VECTORFORGE_",
        env_file=(".env", PROJECT_ROOT / ".env"),
        extra="ignore",
    )

    runs_dir: Path = Path("runs")
    staged_uploads_dir: Path = Path(".staged_uploads")
    max_rounds: int = 3
    experiments_per_round: int = 3
    planner_provider: Literal["mock", "openai"] = "openai"
    openai_model: str = "gpt-5.4"
    openai_api_key: SecretStr | None = Field(
        default="None",
        validation_alias=AliasChoices("VECTORFORGE_OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY"),
    )
    experiment_mode: Literal["mock", "autogluon"] = "autogluon"
    autogluon_fit_strategy: Literal["sequential", "parallel"] = "sequential"
    autogluon_num_cpus: int | None = None
    autogluon_num_gpus: int = 0
    autogluon_num_bag_folds: int | None = 0
    autogluon_num_stack_levels: int | None = 0
    autogluon_save_bag_folds: bool = True
    autogluon_refit_full: bool = False
    autogluon_verbosity: int = 2
    autogluon_max_auto_cpus_per_experiment: int = 2
    autogluon_fit_heartbeat_seconds: float = 5.0
    autogluon_small_data_fast_mode: bool = True
    autogluon_small_data_max_rows: int = 1000
    autogluon_disabled_model_families: list[str] = Field(default_factory=lambda: ["GBM"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
