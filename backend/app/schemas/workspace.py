from __future__ import annotations

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    workspace_id: str | None = Field(default=None, validation_alias="workspaceId")
