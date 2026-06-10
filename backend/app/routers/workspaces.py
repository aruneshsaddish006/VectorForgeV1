from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas.workspace import CreateProjectRequest, CreateWorkspaceRequest, PersistStrategyUseCasesRequest
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


@router.get("/use-cases")
async def list_use_cases(
    workspace_id: str = Query(alias="workspaceId"),
    project_id: str | None = Query(default=None, alias="projectId"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return await workspace_service.list_use_cases_async(current_user["id"], workspace_id, project_id)


@router.post("/use-cases/strategy", status_code=201)
def persist_strategy_use_cases(
    payload: PersistStrategyUseCasesRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return workspace_service.persist_strategy_use_cases(current_user["id"], payload)


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> None:
    workspace_service.delete_workspace(current_user["id"], workspace_id)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> None:
    workspace_service.delete_project(current_user["id"], project_id)


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
