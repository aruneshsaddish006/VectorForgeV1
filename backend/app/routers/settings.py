from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.services import settings_service


router = APIRouter(prefix="/api/settings", tags=["settings"])


class ProviderSettingsRequest(BaseModel):
    workspace_id: str = Field(..., validation_alias="workspaceId")
    provider: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)


class ProviderSettingsTestRequest(BaseModel):
    workspace_id: str = Field(..., validation_alias="workspaceId")
    provider: str
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_settings(
    workspace_id: str = Query(alias="workspaceId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return settings_service.list_settings(current_user["id"], workspace_id)


@router.put("/provider")
def save_provider_settings(
    payload: ProviderSettingsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return settings_service.save_provider_settings(
        current_user["id"],
        payload.workspace_id,
        payload.provider,
        payload.enabled,
        payload.config,
        payload.secrets,
    )


@router.post("/provider/test")
def test_provider_settings(
    payload: ProviderSettingsTestRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return settings_service.test_provider_settings(
        current_user["id"],
        payload.workspace_id,
        payload.provider,
        payload.config,
        payload.secrets,
    )
