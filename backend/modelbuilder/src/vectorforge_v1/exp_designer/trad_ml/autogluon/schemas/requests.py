from pydantic import BaseModel


class ClarificationPayload(BaseModel):
    dataset_path: str | None = None
    target_column: str | None = None
    problem_statement: str | None = None
    business_kpi: str | None = None


class ConfirmationPayload(BaseModel):
    confirmed: bool = True
