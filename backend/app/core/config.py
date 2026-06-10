from __future__ import annotations

from pydantic import BaseModel


class Settings(BaseModel):
    app_title: str = "Forge AI Mock API"
    app_version: str = "0.1.0"
    app_description: str = "Mock backend for the AI Strategy & Use-Case Intelligence Platform."
    cors_origins: list[str] = ["*"]


settings = Settings()
