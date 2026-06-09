from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProblemIntakeRequest(BaseModel):
    problem_statement: str = Field(..., min_length=10)
    kpis: list[str] = Field(default_factory=list)
    domain: str | None = None
    timeline: str | None = None


class ExaRunRequest(BaseModel):
    query: str = Field(..., min_length=10)
    effort: str = "medium"
    input_data: list[dict[str, Any]] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    previous_run_id: str | None = None


class DatasetConfirmRequest(BaseModel):
    target_column: str = "churned"
    apply_quality_fixes: bool = False


class BillingApprovalRequest(BaseModel):
    approval_id: str = "billing_demo"
    approved_by: str = "demo-user"
