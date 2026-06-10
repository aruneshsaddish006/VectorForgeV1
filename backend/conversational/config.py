from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load .env from the conversational/ directory regardless of cwd
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — Vercel AI Gateway
    ai_gateway_api_key: str = ""
    ai_gateway_model: str = ""

    # AWS S3 — field names match the .env variable names exactly
    aws_access_key: str = ""          # AWS_ACCESS_KEY
    aws_secret_access_key: str = ""   # AWS_SECRET_ACCESS_KEY
    aws_session_token: str = ""       # AWS_SESSION_TOKEN (for temporary STS creds)
    aws_default_region: str = "us-east-1"  # AWS_DEFAULT_REGION
    aws_bucket: str = ""              # AWS_BUCKET — full s3://bucket/prefix URL

    @property
    def s3_bucket_name(self) -> str:
        """Extract bucket name from s3://bucket/prefix URL."""
        if self.aws_bucket.startswith("s3://"):
            return self.aws_bucket[5:].split("/")[0]
        return self.aws_bucket

    # Exa dataset search
    exa_api_key: str = ""
    exa_base_url: str = "https://api.exa.ai"

    # LLM defaults
    llm_model: str = "anthropic/claude-sonnet-4-6"
    llm_max_tokens: int = 4096
    # Set to false when behind a corporate TLS-inspection proxy (Zscaler etc.)
    llm_ssl_verify: bool = True

    # Redis — session output cache (read by downstream orchestrators)
    # pydantic-settings reads this from the REDIS_URL env var automatically.
    # Default is for local dev; production uses the REDIS_URL value in .env.
    redis_url: str = "redis://localhost:6379"

    # Model Builder service — invoked after session output is written to Redis.
    # Leave empty to disable the post-completion trigger.
    model_builder_url: str = ""

    # AWS RDS PostgreSQL — LangGraph checkpointing
    # Leave empty to use in-memory checkpointing for local dev/testing
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = ""

    @property
    def postgres_configured(self) -> bool:
        return bool(self.db_host and self.db_password)

    @property
    def postgres_conninfo(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password} sslmode=require"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
