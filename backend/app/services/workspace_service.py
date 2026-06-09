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


def list_datasets(user_id: str, workspace_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)

                params: list[Any] = [workspace_id]
                project_filter = ""
                if project_id:
                    project_filter = "AND p.id = %s"
                    params.append(project_id)

                cursor.execute(
                    f"""
                    SELECT
                      d.id,
                      p.organization_id,
                      p.id AS project_id,
                      p.name AS project_name,
                      d.use_case_id,
                      d.name,
                      d.source_type,
                      d.storage_uri,
                      COALESCE(d.s3_path, d.storage_uri) AS s3_path,
                      d.data_format,
                      d.data_category,
                      d.row_count,
                      d.column_count,
                      d.quality_score,
                      d.target_column,
                      d.task_type,
                      d.status,
                      d.created_at,
                      d.updated_at
                    FROM datasets d
                    LEFT JOIN use_cases uc ON uc.id = d.use_case_id
                    JOIN projects p ON p.id = COALESCE(d.project_id, uc.project_id)
                    WHERE p.organization_id = %s
                    {project_filter}
                    ORDER BY d.created_at DESC
                    """,
                    params,
                )
                return [serialize_dataset(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def list_models(user_id: str, workspace_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)

                params: list[Any] = [workspace_id]
                project_filter = ""
                if project_id:
                    project_filter = "AND p.id = %s"
                    params.append(project_id)

                cursor.execute(
                    f"""
                    SELECT
                      tr.id AS training_run_id,
                      tr.engine,
                      tr.predictor_type,
                      tr.status AS training_status,
                      tr.best_metric_name,
                      tr.best_metric_value,
                      tr.compute_cost,
                      tr.train_time_seconds,
                      tr.sagemaker_job_arn,
                      tr.model_artifact_s3_path,
                      tr.error_message,
                      tr.created_at,
                      tr.started_at,
                      tr.completed_at,
                      p.organization_id,
                      p.id AS project_id,
                      p.name AS project_name,
                      uc.id AS use_case_id,
                      uc.name AS use_case_name,
                      uc.task_type AS use_case_task_type,
                      d.id AS dataset_id,
                      d.name AS dataset_name,
                      COALESCE(d.s3_path, d.storage_uri) AS dataset_s3_path,
                      d.data_format,
                      d.data_category,
                      mle.id AS leaderboard_entry_id,
                      mle.rank,
                      mle.model_name,
                      mle.metric_value,
                      mle.inference_latency_ms,
                      mle.artifact_s3_path,
                      mle.is_best,
                      mle.metadata AS model_metadata
                    FROM training_runs tr
                    JOIN datasets d ON d.id = tr.dataset_id
                    JOIN use_cases uc ON uc.id = tr.use_case_id
                    JOIN projects p ON p.id = COALESCE(tr.project_id, d.project_id, uc.project_id)
                    LEFT JOIN model_leaderboard_entries mle ON mle.training_run_id = tr.id
                    WHERE p.organization_id = %s
                    {project_filter}
                    ORDER BY tr.created_at DESC, mle.rank ASC NULLS LAST
                    """,
                    params,
                )
                return [serialize_model(row) for row in cursor.fetchall()]
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


def serialize_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(dataset["id"]),
        "workspaceId": str(dataset["organization_id"]),
        "projectId": str(dataset["project_id"]),
        "projectName": dataset["project_name"],
        "useCaseId": str(dataset["use_case_id"]) if dataset.get("use_case_id") else None,
        "name": dataset["name"],
        "sourceType": dataset["source_type"],
        "storageUri": dataset.get("storage_uri"),
        "s3Path": dataset.get("s3_path"),
        "dataFormat": dataset.get("data_format") or infer_data_format(dataset.get("s3_path") or dataset.get("storage_uri")),
        "dataCategory": dataset.get("data_category")
        or infer_data_category(dataset.get("data_format") or infer_data_format(dataset.get("s3_path") or dataset.get("storage_uri"))),
        "rowCount": dataset["row_count"],
        "columnCount": dataset["column_count"],
        "qualityScore": dataset.get("quality_score"),
        "targetColumn": dataset.get("target_column"),
        "taskType": dataset.get("task_type"),
        "status": dataset["status"],
        "createdAt": dataset["created_at"].isoformat(),
        "updatedAt": dataset["updated_at"].isoformat(),
    }


def serialize_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "trainingRunId": str(model["training_run_id"]),
        "workspaceId": str(model["organization_id"]),
        "projectId": str(model["project_id"]),
        "projectName": model["project_name"],
        "useCaseId": str(model["use_case_id"]),
        "useCaseName": model["use_case_name"],
        "useCaseTaskType": model["use_case_task_type"],
        "datasetId": str(model["dataset_id"]),
        "datasetName": model["dataset_name"],
        "datasetS3Path": model.get("dataset_s3_path"),
        "datasetFormat": model.get("data_format") or infer_data_format(model.get("dataset_s3_path")),
        "datasetCategory": model.get("data_category")
        or infer_data_category(model.get("data_format") or infer_data_format(model.get("dataset_s3_path"))),
        "engine": model["engine"],
        "predictorType": model["predictor_type"],
        "trainingStatus": model["training_status"],
        "bestMetricName": model.get("best_metric_name"),
        "bestMetricValue": float(model["best_metric_value"]) if model.get("best_metric_value") is not None else None,
        "computeCost": float(model["compute_cost"]) if model.get("compute_cost") is not None else None,
        "trainTimeSeconds": model.get("train_time_seconds"),
        "sagemakerJobArn": model.get("sagemaker_job_arn"),
        "modelArtifactS3Path": model.get("model_artifact_s3_path"),
        "errorMessage": model.get("error_message"),
        "leaderboardEntryId": str(model["leaderboard_entry_id"]) if model.get("leaderboard_entry_id") else None,
        "rank": model.get("rank"),
        "modelName": model.get("model_name"),
        "metricValue": float(model["metric_value"]) if model.get("metric_value") is not None else None,
        "inferenceLatencyMs": model.get("inference_latency_ms"),
        "artifactS3Path": model.get("artifact_s3_path") or model.get("model_artifact_s3_path"),
        "isBest": model.get("is_best") or False,
        "metadata": model.get("model_metadata") or {},
        "createdAt": model["created_at"].isoformat(),
        "startedAt": model["started_at"].isoformat() if model.get("started_at") else None,
        "completedAt": model["completed_at"].isoformat() if model.get("completed_at") else None,
    }


def infer_data_format(path: str | None) -> str | None:
    if not path:
        return None

    lowered = path.lower().split("?", 1)[0]
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith(".pdf"):
        return "pdf"
    return None


def infer_data_category(data_format: str | None) -> str | None:
    if data_format == "csv":
        return "structured"
    if data_format == "pdf":
        return "unstructured"
    return None
