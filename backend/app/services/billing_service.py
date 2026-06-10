from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row

from app.db import connect_db
from app.services.auth_service import db_error
from app.services import settings_service
from app.services.workspace_service import ensure_workspace_access


PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "priceMonthly": 0,
        "summary": "Try one use case end-to-end",
        "features": ["1 use case", "Bring your own data", "Community support"],
        "limits": {"useCases": 1, "exaDatasets": 0, "ragTrials": 0, "trainingRuns": 1},
        "stripeCatalogEnv": None,
    },
    "pro": {
        "name": "Pro",
        "priceMonthly": 49,
        "summary": "3 use cases · 10 Exa datasets · 5 RAG trials",
        "features": ["3 use cases", "10 Exa datasets", "5 RAG trials", "Stripe usage approvals"],
        "limits": {"useCases": 3, "exaDatasets": 10, "ragTrials": 5, "trainingRuns": 10},
        "stripeCatalogEnv": "STRIPE_PRO_PRICE_ID",
    },
    "enterprise": {
        "name": "Enterprise",
        "priceMonthly": 299,
        "summary": "Unlimited · custom models · SLA",
        "features": ["Unlimited use cases", "Custom models", "SLA", "Private deployment support"],
        "limits": {"useCases": None, "exaDatasets": None, "ragTrials": None, "trainingRuns": None},
        "stripeCatalogEnv": "STRIPE_ENTERPRISE_PRICE_ID",
    },
}


def get_billing_summary(user_id: str, workspace_id: str) -> dict[str, Any]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                account = _ensure_billing_account(cursor, workspace_id)
                plan_id = _normalize_plan(account.get("plan"))
                period_start = _current_period_start()

                usage = _load_usage(cursor, workspace_id, period_start)
                usage["useCases"] = _count_use_cases(cursor, workspace_id)

                return {
                    "workspaceId": workspace_id,
                    "subscription": {
                        "plan": plan_id,
                        "status": "active" if plan_id != "free" else "free",
                        "stripeCustomerId": account.get("stripe_customer_id"),
                        "stripeSubscriptionId": account.get("stripe_subscription_id"),
                        "currentPeriodStart": period_start.isoformat(),
                        "currentPeriodEnd": None,
                    },
                    "plans": _plans_for_client(_stripe_catalog_config(cursor, workspace_id)),
                    "usage": _usage_for_client(usage, PLAN_CATALOG[plan_id]["limits"]),
                }
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def create_checkout_session(user_id: str, workspace_id: str, plan: str) -> dict[str, str]:
    plan_id = _normalize_plan(plan)
    if plan_id == "free":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Free plan does not require checkout.")

    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                account = _ensure_billing_account(cursor, workspace_id)
                customer_id = account.get("stripe_customer_id")
                stripe_values = _stripe_settings(cursor, workspace_id)
                catalog_id = _catalog_id_for_plan(plan_id, stripe_values["config"])
                secret_key = _stripe_secret_key(stripe_values["secrets"])

        price_id = _resolve_checkout_price_id(catalog_id, secret_key)

        payload = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": f"{_frontend_url()}/dashboard?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{_frontend_url()}/dashboard?billing=cancelled",
            "client_reference_id": workspace_id,
            "metadata[workspace_id]": workspace_id,
            "metadata[plan]": plan_id,
        }
        if customer_id:
            payload["customer"] = customer_id

        session = _stripe_request("/v1/checkout/sessions", payload, secret_key)
        url = session.get("url")
        if not url:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe did not return a checkout URL.")
        return {"url": str(url)}
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def create_portal_session(user_id: str, workspace_id: str) -> dict[str, str]:
    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                ensure_workspace_access(cursor, user_id, workspace_id)
                account = _ensure_billing_account(cursor, workspace_id)
                customer_id = account.get("stripe_customer_id")
                secret_key = _stripe_secret_key(_stripe_settings(cursor, workspace_id)["secrets"])

        if not customer_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No Stripe customer is linked to this workspace.")

        session = _stripe_request(
            "/v1/billing_portal/sessions",
            {"customer": customer_id, "return_url": f"{_frontend_url()}/dashboard?billing=portal"},
            secret_key,
        )
        url = session.get("url")
        if not url:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe did not return a portal URL.")
        return {"url": str(url)}
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def _ensure_billing_account(cursor: psycopg.Cursor, workspace_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO billing_accounts (organization_id, plan, exa_credit_allowance)
        VALUES (%s, 'free', 0)
        ON CONFLICT (organization_id) DO NOTHING
        """,
        (workspace_id,),
    )
    cursor.execute(
        """
        SELECT id, organization_id, stripe_customer_id, stripe_subscription_id, plan, exa_credit_allowance, created_at, updated_at
        FROM billing_accounts
        WHERE organization_id = %s
        """,
        (workspace_id,),
    )
    account = cursor.fetchone()
    if not account:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Billing account could not be loaded.")
    return account


def _load_usage(cursor: psycopg.Cursor, workspace_id: str, period_start: datetime) -> dict[str, Decimal]:
    cursor.execute(
        """
        SELECT
          COALESCE(SUM(total_cost), 0) AS spend,
          COALESCE(SUM(units) FILTER (WHERE event_type IN ('exa_acu', 'exa_search')), 0) AS exa_datasets,
          COALESCE(SUM(units) FILTER (WHERE event_type = 'autorag_compute'), 0) AS rag_trials,
          COALESCE(SUM(units) FILTER (WHERE event_type = 'autogluon_compute'), 0) AS training_runs,
          COALESCE(SUM(units) FILTER (WHERE event_type = 'deployment_runtime'), 0) AS deployment_runtime
        FROM usage_events
        WHERE organization_id = %s AND created_at >= %s
        """,
        (workspace_id, period_start),
    )
    row = cursor.fetchone() or {}
    return {
        "spend": row.get("spend") or Decimal("0"),
        "exaDatasets": row.get("exa_datasets") or Decimal("0"),
        "ragTrials": row.get("rag_trials") or Decimal("0"),
        "trainingRuns": row.get("training_runs") or Decimal("0"),
        "deploymentRuntime": row.get("deployment_runtime") or Decimal("0"),
    }


def _count_use_cases(cursor: psycopg.Cursor, workspace_id: str) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM use_cases uc
        JOIN projects p ON p.id = uc.project_id
        WHERE p.organization_id = %s AND uc.status <> 'archived'
        """,
        (workspace_id,),
    )
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def _usage_for_client(usage: dict[str, Decimal | int], limits: dict[str, int | None]) -> dict[str, Any]:
    return {
        "periodSpend": float(usage["spend"]),
        "items": [
            _usage_item("Use cases", "useCases", usage["useCases"], limits["useCases"], "Generated use cases in this workspace"),
            _usage_item("Exa datasets", "exaDatasets", usage["exaDatasets"], limits["exaDatasets"], "Web datasets built or enriched"),
            _usage_item("RAG trials", "ragTrials", usage["ragTrials"], limits["ragTrials"], "AutoRAG optimization trials"),
            _usage_item("Training runs", "trainingRuns", usage["trainingRuns"], limits["trainingRuns"], "AutoGluon/model training jobs"),
        ],
    }


def _usage_item(label: str, key: str, value: Decimal | int, limit: int | None, description: str) -> dict[str, Any]:
    numeric_value = float(value)
    return {
        "key": key,
        "label": label,
        "value": numeric_value,
        "limit": limit,
        "unit": "runs" if key == "trainingRuns" else "count",
        "description": description,
    }


def _plans_for_client(stripe_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    stripe_config = stripe_config or {}
    return [
        {
            "id": plan_id,
            "name": config["name"],
            "priceMonthly": config["priceMonthly"],
            "summary": config["summary"],
            "features": config["features"],
            "limits": config["limits"],
            "checkoutEnabled": bool(plan_id == "free" or _catalog_id_for_plan(plan_id, stripe_config, required=False)),
        }
        for plan_id, config in PLAN_CATALOG.items()
    ]


def _normalize_plan(plan: str | None) -> str:
    value = (plan or "free").strip().lower()
    return value if value in PLAN_CATALOG else "free"


def _current_period_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL") or os.getenv("NEXT_PUBLIC_APP_URL") or "http://localhost:3000"


def _stripe_settings(cursor: psycopg.Cursor, workspace_id: str) -> dict[str, Any]:
    return settings_service.get_provider_values(cursor, workspace_id, "stripe")


def _stripe_catalog_config(cursor: psycopg.Cursor, workspace_id: str) -> dict[str, Any]:
    return _stripe_settings(cursor, workspace_id)["config"]


def _catalog_id_for_plan(plan_id: str, stripe_config: dict[str, Any], required: bool = True) -> str:
    if plan_id == "free":
        return ""
    config_key = "pro_catalog_id" if plan_id == "pro" else "enterprise_catalog_id"
    env_name = str(PLAN_CATALOG[plan_id]["stripeCatalogEnv"])
    catalog_id = str(stripe_config.get(config_key) or os.getenv(env_name) or "").strip()
    if required and not catalog_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe catalog item is not configured. Save {config_key} in Settings or set {env_name}.",
        )
    return catalog_id


def _stripe_secret_key(secrets: dict[str, Any]) -> str:
    secret_key = str(secrets.get("secret_key") or os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Save the Stripe secret key in Settings or set STRIPE_SECRET_KEY.",
        )
    return secret_key


def _resolve_checkout_price_id(catalog_id: str, secret_key: str) -> str:
    value = catalog_id.strip()
    if value.startswith("price_"):
        return value
    if value.startswith("prod_"):
        prices = _stripe_request(
            "/v1/prices",
            {
                "product": value,
                "active": "true",
                "type": "recurring",
                "limit": "10",
            },
            secret_key,
            method="GET",
        )
        price_id = _select_monthly_price(prices.get("data") or [])
        if price_id:
            return price_id
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stripe product {value} does not have an active recurring price. Create a monthly price in Stripe sandbox or set a price_ ID.",
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Stripe catalog item must be a price_ ID or prod_ ID.",
    )


def _select_monthly_price(prices: list[dict[str, Any]]) -> str | None:
    recurring_prices = [price for price in prices if price.get("type") == "recurring" and price.get("active")]
    for price in recurring_prices:
        recurring = price.get("recurring") or {}
        if recurring.get("interval") == "month":
            price_id = price.get("id")
            return str(price_id) if price_id else None
    for price in recurring_prices:
        price_id = price.get("id")
        if price_id:
            return str(price_id)
    return None


def _stripe_request(path: str, payload: dict[str, str], secret_key: str, method: str = "POST") -> dict[str, Any]:
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
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") or str(exc)
        raise HTTPException(status_code=exc.code, detail=f"Stripe error: {detail}") from exc
    except URLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe network error: {exc.reason}") from exc
