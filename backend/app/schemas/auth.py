from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120, validation_alias=AliasChoices("full_name", "fullName", "name"))
    email: str = Field(..., min_length=5, max_length=254)
    company: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    email: str = Field(default="demo.user@gmail.com", min_length=5, max_length=254)
    full_name: str = Field(
        default="Demo Google User",
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("full_name", "fullName", "name"),
    )
    provider_user_id: str | None = Field(default=None, validation_alias=AliasChoices("provider_user_id", "providerUserId"))
    avatar_url: str | None = Field(default=None, validation_alias=AliasChoices("avatar_url", "avatarUrl"))
    company: str = Field(default="Google Workspace", min_length=2, max_length=120)
