from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas.workspace import CreateProjectRequest, CreateWorkspaceRequest
from app.services import workspace_service


router = APIRouter(prefix="/api", tags=["workspaces"])


@router.post("/workspaces", status_code=201)
def create_workspace(payload: CreateWorkspaceRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return workspace_service.create_workspace(current_user["id"], payload)


@router.get("/workspaces")
def list_workspaces(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    return workspace_service.list_workspaces(current_user["id"])


@router.post("/projects", status_code=201)
def create_project(payload: CreateProjectRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return workspace_service.create_project(current_user["id"], payload)


@router.get("/projects")
def list_projects(
    workspace_id: str = Query(alias="workspaceId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return workspace_service.list_projects(current_user["id"], workspace_id)


@router.get("/datasets")
def list_datasets(
    workspace_id: str = Query(alias="workspaceId"),
    project_id: str | None = Query(default=None, alias="projectId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return workspace_service.list_datasets(current_user["id"], workspace_id, project_id)


@router.get("/models")
def list_models(
    workspace_id: str = Query(alias="workspaceId"),
    project_id: str | None = Query(default=None, alias="projectId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return workspace_service.list_models(current_user["id"], workspace_id, project_id)


@router.get("/workspaces/{workspace_id}/projects/{project_id}/assets")
def project_assets(
    workspace_id: str,
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return workspace_service.get_project_assets(current_user["id"], workspace_id, project_id)
