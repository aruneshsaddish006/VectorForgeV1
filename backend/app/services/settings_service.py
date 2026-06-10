from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db import connect_db
from app.services.auth_service import db_error
from app.services.workspace_service import ensure_workspace_access


PROVIDER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "exa": {
        "name": "Exa",
        "description": "Web search and dataset sourcing for agentic data workflows.",
        "secrets": {"api_key": "EXA API key"},
        "config": {"result_count": "Default result count"},
    },
    "vercel_ai": {
        "name": "Vercel AI Gateway",
        "description": "OpenAI-compatible gateway for model calls routed through Vercel.",
        "secrets": {"api_key": "Vercel AI Gateway key"},
        "config": {"base_url": "Gateway base URL", "model": "Default model"},
    },
    "openai": {
        "name": "OpenAI",
        "description": "Direct OpenAI API fallback for planning, schema generation, and embeddings.",
        "secrets": {"api_key": "OpenAI API key"},
        "config": {"model": "Default model", "embedding_model": "Embedding model"},
    },
    "stripe": {
        "name": "Stripe",
        "description": "Checkout, customer portal, subscriptions, and usage billing.",
        "secrets": {"secret_key": "Stripe secret key", "webhook_secret": "Webhook signing secret"},
        "config": {"pro_catalog_id": "Pro price or product ID", "enterprise_catalog_id": "Enterprise price or product ID"},
    },
    "aws": {
        "name": "AWS",
        "description": "S3 dataset storage and AWS-hosted model artifacts.",
        "secrets": {"access_key_id": "Access key ID", "secret_access_key": "Secret access key"},
        "config": {"region": "AWS region", "s3_bucket": "S3 bucket"},
    },
}

DEFAULT_CONFIG: dict[str, dict[str, str]] = {
    "exa": {"result_count": "10"},
    "vercel_ai": {"base_url": "https://ai-gateway.vercel.sh/v1", "model": "openai/gpt-4o-mini"},
    "openai": {"model": "gpt-4o-mini", "embedding_model": "text-embedding-3-small"},
    "stripe": {
        "pro_catalog_id": os.getenv("STRIPE_PRO_PRICE_ID", ""),
        "enterprise_catalog_id": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", ""),
    },
    "aws": {"region": os.getenv("AWS_REGION", "us-west-2"), "s3_bucket": os.getenv("S3_BUCKET_NAME", "")},
}

ENV_FALLBACKS: dict[str, dict[str, str]] = {
    "exa": {"api_key": "EXA_API_KEY"},
    "vercel_ai": {"api_key": "VECTORFORGE_AI_GATEWAY_API_KEY"},
    "openai": {"api_key": "OPENAI_API_KEY"},
    "stripe": {"secret_key": "STRIPE_SECRET_KEY", "webhook_secret": "STRIPE_WEBHOOK_SECRET"},
    "aws": {"access_key_id": "AWS_ACCESS_KEY_ID", "secret_access_key": "AWS_SECRET_ACCESS_KEY"},
}


def list_settings(user_id: str, workspace_id: str) -> dict[str, Any]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                ensure_settings_table(cursor)
                rows = load_settings_rows(cursor, workspace_id)
                return {
                    "workspaceId": workspace_id,
                    "providers": [serialize_provider(provider_id, rows.get(provider_id)) for provider_id in PROVIDER_DEFINITIONS],
                }
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def save_provider_settings(
    user_id: str,
    workspace_id: str,
    provider: str,
    enabled: bool,
    config: dict[str, Any],
    secrets: dict[str, Any],
) -> dict[str, Any]:
    provider_id = normalize_provider(provider)
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                ensure_settings_table(cursor)
                existing = load_settings_row(cursor, workspace_id, provider_id)
                next_config = merge_allowed_config(provider_id, existing.get("config") if existing else {}, config)
                next_secrets = merge_allowed_secrets(provider_id, existing.get("secrets") if existing else {}, secrets)

                cursor.execute(
                    """
                    INSERT INTO integration_settings (organization_id, provider, enabled, config, secrets, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (organization_id, provider)
                    DO UPDATE SET
                      enabled = EXCLUDED.enabled,
                      config = EXCLUDED.config,
                      secrets = EXCLUDED.secrets,
                      updated_by = EXCLUDED.updated_by,
                      updated_at = now()
                    RETURNING organization_id, provider, enabled, config, secrets, updated_at
                    """,
                    (workspace_id, provider_id, enabled, Jsonb(next_config), Jsonb(next_secrets), user_id),
                )
                row = cursor.fetchone()
                return serialize_provider(provider_id, row)
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def test_provider_settings(
    user_id: str,
    workspace_id: str,
    provider: str,
    config: dict[str, Any] | None = None,
    secrets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_id = normalize_provider(provider)
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                ensure_settings_table(cursor)
                existing = load_settings_row(cursor, workspace_id, provider_id) or {}
                merged_config = merge_allowed_config(provider_id, existing.get("config") or {}, config or {})
                merged_secrets = merge_allowed_secrets(provider_id, existing.get("secrets") or {}, secrets or {})

        status_message = run_provider_check(provider_id, merged_config, merged_secrets)
        return {"provider": provider_id, "ok": True, "message": status_message}
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def get_provider_values(cursor: psycopg.Cursor, workspace_id: str, provider: str) -> dict[str, Any]:
    provider_id = normalize_provider(provider)
    ensure_settings_table(cursor)
    row = load_settings_row(cursor, workspace_id, provider_id) or {}
    return {
        "enabled": row.get("enabled", True),
        "config": {**DEFAULT_CONFIG.get(provider_id, {}), **(row.get("config") or {})},
        "secrets": provider_secrets_with_env(provider_id, row.get("secrets") or {}),
    }


def ensure_settings_table(cursor: psycopg.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_settings (
          organization_id UUID NOT NULL,
          provider TEXT NOT NULL,
          enabled BOOLEAN NOT NULL DEFAULT TRUE,
          config JSONB NOT NULL DEFAULT '{}'::jsonb,
          secrets JSONB NOT NULL DEFAULT '{}'::jsonb,
          updated_by UUID NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (organization_id, provider)
        )
        """
    )


def load_settings_rows(cursor: psycopg.Cursor, workspace_id: str) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT organization_id, provider, enabled, config, secrets, updated_at
        FROM integration_settings
        WHERE organization_id = %s
        """,
        (workspace_id,),
    )
    return {row["provider"]: row for row in cursor.fetchall()}


def load_settings_row(cursor: psycopg.Cursor, workspace_id: str, provider: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT organization_id, provider, enabled, config, secrets, updated_at
        FROM integration_settings
        WHERE organization_id = %s AND provider = %s
        """,
        (workspace_id, provider),
    )
    return cursor.fetchone()


def serialize_provider(provider_id: str, row: dict[str, Any] | None) -> dict[str, Any]:
    definition = PROVIDER_DEFINITIONS[provider_id]
    config = {**DEFAULT_CONFIG.get(provider_id, {}), **((row or {}).get("config") or {})}
    stored_secrets = (row or {}).get("secrets") or {}
    secrets = provider_secrets_with_env(provider_id, stored_secrets)
    return {
        "id": provider_id,
        "name": definition["name"],
        "description": definition["description"],
        "enabled": bool((row or {}).get("enabled", True)),
        "configured": all(bool(secrets.get(secret_name)) for secret_name in definition["secrets"]),
        "config": {key: str(config.get(key, "")) for key in definition["config"]},
        "secretFields": [
            {
                "key": key,
                "label": label,
                "configured": bool(secrets.get(key)),
                "masked": mask_secret(secrets.get(key)),
                "source": "workspace" if stored_secrets.get(key) else "environment" if env_secret(provider_id, key) else "missing",
            }
            for key, label in definition["secrets"].items()
        ],
        "configFields": [{"key": key, "label": label} for key, label in definition["config"].items()],
        "updatedAt": (row or {}).get("updated_at").isoformat() if (row or {}).get("updated_at") else None,
    }


def provider_secrets_with_env(provider_id: str, stored: dict[str, Any]) -> dict[str, str]:
    definition = PROVIDER_DEFINITIONS[provider_id]
    return {
        key: str(stored.get(key) or env_secret(provider_id, key) or "")
        for key in definition["secrets"]
    }


def env_secret(provider_id: str, key: str) -> str:
    env_name = ENV_FALLBACKS.get(provider_id, {}).get(key)
    return os.getenv(env_name or "", "")


def merge_allowed_config(provider_id: str, existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, str]:
    allowed = PROVIDER_DEFINITIONS[provider_id]["config"]
    merged = {key: str(existing.get(key) or DEFAULT_CONFIG.get(provider_id, {}).get(key, "")) for key in allowed}
    for key, value in updates.items():
        if key in allowed:
            merged[key] = "" if value is None else str(value).strip()
    return merged


def merge_allowed_secrets(provider_id: str, existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, str]:
    allowed = PROVIDER_DEFINITIONS[provider_id]["secrets"]
    merged = {key: str(existing.get(key) or "") for key in allowed}
    for key, value in updates.items():
        if key in allowed and value is not None and str(value).strip():
            merged[key] = str(value).strip()
    return merged


def normalize_provider(provider: str) -> str:
    provider_id = provider.strip().lower()
    if provider_id not in PROVIDER_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported settings provider.")
    return provider_id


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return f"{value[:4]}••••{value[-4:]}"


def run_provider_check(provider_id: str, config: dict[str, Any], secrets: dict[str, Any]) -> str:
    if provider_id == "exa":
        api_key = required_secret(secrets, "api_key", "EXA API key")
        response = json_request(
            "https://api.exa.ai/search",
            {"query": "VectorForge connectivity test", "numResults": 1},
            headers={"x-api-key": api_key},
        )
        if not isinstance(response.get("results"), list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Exa response did not include results.")
        return "Exa key is valid and search returned a response."

    if provider_id == "vercel_ai":
        api_key = required_secret(secrets, "api_key", "Vercel AI Gateway key")
        base_url = str(config.get("base_url") or "https://ai-gateway.vercel.sh/v1").rstrip("/")
        json_request(f"{base_url}/models", None, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
        return "Vercel AI Gateway key is valid and the models endpoint responded."

    if provider_id == "openai":
        api_key = required_secret(secrets, "api_key", "OpenAI API key")
        json_request("https://api.openai.com/v1/models", None, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
        return "OpenAI key is valid and the models endpoint responded."

    if provider_id == "stripe":
        secret_key = required_secret(secrets, "secret_key", "Stripe secret key")
        stripe_request("/v1/account", {}, secret_key, method="GET")
        return "Stripe secret key is valid and account details are reachable."

    if provider_id == "aws":
        required_secret(secrets, "access_key_id", "AWS access key ID")
        required_secret(secrets, "secret_access_key", "AWS secret access key")
        if not config.get("region"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AWS region is required.")
        if not config.get("s3_bucket"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="S3 bucket is required.")
        return "AWS settings are complete. Bucket access is validated by dataset upload/list operations."

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported settings provider.")


def required_secret(secrets: dict[str, Any], key: str, label: str) -> str:
    value = str(secrets.get(key) or "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{label} is required.")
    return value


def json_request(url: str, payload: dict[str, Any] | None, headers: dict[str, str], method: str = "POST") -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json", **headers},
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") or str(exc)
        raise HTTPException(status_code=exc.code, detail=f"Provider validation failed: {detail}") from exc
    except URLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Provider validation network error: {exc.reason}") from exc


def stripe_request(path: str, payload: dict[str, str], secret_key: str, method: str = "POST") -> dict[str, Any]:
    encoded = urlencode(payload).encode("utf-8")
    auth = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("ascii")
    url = f"https://api.stripe.com{path}"
    request_data = encoded
    if method == "GET":
        url = f"{url}?{encoded.decode('utf-8')}" if payload else url
        request_data = None

    request = Request(
        url,
        data=request_data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Stripe-Version": "2025-02-24.acacia",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") or str(exc)
        raise HTTPException(status_code=exc.code, detail=f"Stripe validation failed: {detail}") from exc
    except URLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe validation network error: {exc.reason}") from exc
