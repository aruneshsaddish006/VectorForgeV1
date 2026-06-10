from __future__ import annotations

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    workspace_id: str | None = Field(default=None, validation_alias="workspaceId")


class StrategyUseCaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    task_type: str = Field(..., min_length=1, max_length=120, validation_alias="taskType")
    business_problem: str = Field(default="", validation_alias="businessProblem")
    kpis: list[str] = Field(default_factory=list)


class PersistStrategyUseCasesRequest(BaseModel):
    workspace_id: str = Field(..., validation_alias="workspaceId")
    project_id: str = Field(..., validation_alias="projectId")
    use_cases: list[StrategyUseCaseRequest] = Field(..., validation_alias="useCases")
