from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.services import billing_service


router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    workspace_id: str = Field(..., validation_alias="workspaceId")
    plan: str = Field(..., min_length=2, max_length=32)


class PortalRequest(BaseModel):
    workspace_id: str = Field(..., validation_alias="workspaceId")


@router.get("/summary")
def billing_summary(
    workspace_id: str = Query(alias="workspaceId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return billing_service.get_billing_summary(current_user["id"], workspace_id)


@router.post("/checkout")
def create_checkout(
    payload: CheckoutRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    return billing_service.create_checkout_session(current_user["id"], payload.workspace_id, payload.plan)


@router.post("/portal")
def create_portal(
    payload: PortalRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    return billing_service.create_portal_session(current_user["id"], payload.workspace_id)
