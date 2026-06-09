from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vectorforge_v1.llm_gateway import DEFAULT_NARRATIVE_AI_GATEWAY_MODEL


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ArtifactForgeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VECTORFORGE_",
        env_file=(".env", PROJECT_ROOT / ".env"),
        extra="ignore",
    )

    smoke_backend: Literal["opensandbox", "vercel", "local"] = "local"

    # When api_key is None/empty the local opensandbox-server skips auth automatically
    opensandbox_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VECTORFORGE_OPENSANDBOX_API_KEY", "OPENSANDBOX_API_KEY"),
    )
    # Override to point at a local server, e.g. VECTORFORGE_OPENSANDBOX_DOMAIN=localhost:8080
    opensandbox_domain: str = Field(
        default="localhost:8080",
        validation_alias=AliasChoices("VECTORFORGE_OPENSANDBOX_DOMAIN", "OPENSANDBOX_DOMAIN"),
    )

    artifact_smoke_timeout_seconds: int = 240
    smoke_depth: Literal["full", "contract"] = "full"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VECTORFORGE_OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY"),
    )
    openai_model: str = "gpt-4o-mini"
    ai_gateway_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VECTORFORGE_AI_GATEWAY_API_KEY",
            "AI_GATEWAY_API_KEY",
            "VERCEL_OIDC_TOKEN",
        ),
    )
    ai_gateway_model: str = Field(
        default=DEFAULT_NARRATIVE_AI_GATEWAY_MODEL,
        validation_alias=AliasChoices(
            "VECTORFORGE_NARRATIVE_AI_GATEWAY_MODEL",
            "NARRATIVE_AI_GATEWAY_MODEL",
            "VECTORFORGE_AI_GATEWAY_MODEL",
            "AI_GATEWAY_MODEL",
        ),
    )

    @field_validator("opensandbox_domain", mode="before")
    @classmethod
    def _default_blank_opensandbox_domain(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "localhost:8080"
        return value


@lru_cache
def get_settings() -> ArtifactForgeSettings:
    return ArtifactForgeSettings()
