from __future__ import annotations

from typing import Any

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row

from app.db import connect_db
from app.schemas.workspace import CreateProjectRequest, CreateWorkspaceRequest
from app.services.demo_data import DEMO_WORKSPACE
from app.services.auth_service import db_error, get_primary_organization, make_slug, reserve_slug


def create_workspace(user_id: str, payload: CreateWorkspaceRequest) -> dict[str, Any]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                slug = reserve_slug(cursor, make_slug(payload.name))
                cursor.execute(
                    """
                    INSERT INTO organizations (name, slug, plan)
                    VALUES (%s, %s, 'free')
                    RETURNING id, name, plan
                    """,
                    (payload.name.strip(), slug),
                )
                workspace = cursor.fetchone()
                cursor.execute(
                    """
                    INSERT INTO workspace_members (organization_id, user_id, role)
                    VALUES (%s, %s, 'owner')
                    """,
                    (workspace["id"], user_id),
                )

        return serialize_workspace(workspace)
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def list_workspaces(user_id: str) -> list[dict[str, Any]]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT o.id, o.name, o.plan
                    FROM organizations o
                    JOIN workspace_members wm ON wm.organization_id = o.id
                    WHERE wm.user_id = %s
                    ORDER BY wm.created_at DESC
                    """,
                    (user_id,),
                )
                return [serialize_workspace(row) for row in cursor.fetchall()]
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def create_project(user_id: str, payload: CreateProjectRequest) -> dict[str, Any]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                workspace_id = payload.workspace_id
                if not workspace_id:
                    primary_workspace = get_primary_organization(cursor, user_id)
                    if not primary_workspace:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Create a workspace before creating a project.",
                        )
                    workspace_id = str(primary_workspace["id"])

                cursor.execute(
                    """
                    SELECT wm.role, o.id, o.name, o.plan
                    FROM workspace_members wm
                    JOIN organizations o ON o.id = wm.organization_id
                    WHERE wm.user_id = %s AND wm.organization_id = %s
                    """,
                    (user_id, workspace_id),
                )
                membership = cursor.fetchone()
                if not membership:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have access to this workspace.",
                    )

                cursor.execute(
                    """
                    INSERT INTO projects (organization_id, name, description, status, created_by)
                    VALUES (%s, %s, %s, 'active', %s)
                    RETURNING id, organization_id, name, description, status, created_at
                    """,
                    (workspace_id, payload.name.strip(), payload.description, user_id),
                )
                project = cursor.fetchone()

        return serialize_project(project)
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def list_projects(user_id: str, workspace_id: str) -> list[dict[str, Any]]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                cursor.execute(
                    """
                    SELECT id, organization_id, name, description, status, created_at
                    FROM projects
                    WHERE organization_id = %s
                    ORDER BY created_at DESC
                    """,
                    (workspace_id,),
                )
                return [serialize_project(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def get_project_assets(user_id: str, workspace_id: str, project_id: str) -> dict[str, Any]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                cursor.execute(
                    """
                    SELECT id, organization_id, name, description, status, created_at
                    FROM projects
                    WHERE id = %s AND organization_id = %s
                    """,
                    (project_id, workspace_id),
                )
                project = cursor.fetchone()
                if not project:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        return {
            "workspaceId": workspace_id,
            "project": serialize_project(project),
            "dataset": DEMO_WORKSPACE["dataset"],
            "training": DEMO_WORKSPACE["training"],
            "models": DEMO_WORKSPACE["training"]["leaderboard"],
        }
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def ensure_workspace_access(cursor: psycopg.Cursor, user_id: str, workspace_id: str) -> None:
    cursor.execute(
        """
        SELECT 1
        FROM workspace_members
        WHERE user_id = %s AND organization_id = %s
        """,
        (user_id, workspace_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this workspace.")


def serialize_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(workspace["id"]),
        "name": workspace["name"],
        "plan": workspace["plan"],
    }


def serialize_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(project["id"]),
        "workspaceId": str(project["organization_id"]),
        "name": project["name"],
        "description": project.get("description"),
        "status": project["status"],
        "createdAt": project["created_at"].isoformat(),
    }
