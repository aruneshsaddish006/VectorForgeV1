from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

from app.schemas.auth import GoogleAuthRequest, LoginRequest, SignupRequest
from app.services import auth_service


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", status_code=201)
def signup(payload: SignupRequest) -> dict[str, Any]:
    return auth_service.signup(payload)


@router.post("/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    return auth_service.login(payload)


@router.post("/google")
def google_auth(payload: GoogleAuthRequest) -> dict[str, Any]:
    return auth_service.google_auth(payload)


@router.post("/logout")
def logout(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    auth_service.logout(current_user["token"])
    return {"status": "logged_out"}
