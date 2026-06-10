from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProblemCategory(str, Enum):
    TRADITIONAL = "traditional"
    GENAI = "genai"


class ExperimentEngine(str, Enum):
    AUTOGLUON = "autogluon"
    AUTORAG = "autorag"


class AutoGluonTaskType(str, Enum):
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"
    TIME_SERIES_FORECASTING = "time_series_forecasting"
    TEXT_CLASSIFICATION = "text_classification"
    IMAGE_CLASSIFICATION = "image_classification"


class AutoRAGTaskType(str, Enum):
    QA = "rag_question_answering"
    RETRIEVAL = "rag_document_retrieval"


class DatasetSourceType(str, Enum):
    UPLOAD = "upload"
    DISCOVER = "discover"
    SKIP = "skip"


class InterruptType(str, Enum):
    CLARIFICATION = "clarification"
    SUB_PROBLEM_CONFIRMATION = "sub_problem_confirmation"
    DATASET_SOURCE_CHOICE = "dataset_source_choice"
    AWAITING_UPLOAD = "awaiting_upload"
    EXA_RESULTS_REVIEW = "exa_results_review"
    DATASET_COST_APPROVAL = "dataset_cost_approval"
    SCHEMA_CONFIRMATION = "schema_confirmation"
    FINAL_REVIEW = "final_review"


class ConversationStatus(str, Enum):
    INTAKE = "intake"
    DECOMPOSING = "decomposing"
    DATASET_SOURCING = "dataset_sourcing"
    COMPILING = "compiling"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Column inference
# ---------------------------------------------------------------------------

class InferredColumn(BaseModel):
    inferred_name: str
    type: str
    confidence: Literal["high", "medium", "low"]
    reason: str


class InferredColumns(BaseModel):
    # AutoGluon
    label_column: Optional[InferredColumn] = None
    target_column: Optional[InferredColumn] = None
    timestamp_column: Optional[InferredColumn] = None
    item_id_column: Optional[InferredColumn] = None
    text_column: Optional[InferredColumn] = None
    image_path_column: Optional[InferredColumn] = None
    class_labels: Optional[list[str]] = None
    # AutoRAG corpus
    corpus_doc_id_column: Optional[InferredColumn] = None
    corpus_content_column: Optional[InferredColumn] = None
    # AutoRAG QA eval
    qa_query_id_column: Optional[InferredColumn] = None
    qa_query_column: Optional[InferredColumn] = None
    qa_retrieval_gt_column: Optional[InferredColumn] = None
    qa_generation_gt_column: Optional[InferredColumn] = None


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class SchemaColumn(BaseModel):
    column: str
    type: str
    null_pct: float
    source: str = ""


class DatasetSource(BaseModel):
    type: DatasetSourceType
    # AutoGluon single-file
    s3_path: Optional[str] = None
    row_count: Optional[int] = None
    feature_count: Optional[int] = None
    # AutoRAG two-file (corpus + QA)
    corpus_s3_path: Optional[str] = None
    qa_s3_path: Optional[str] = None
    corpus_row_count: Optional[int] = None
    qa_row_count: Optional[int] = None
    quality_score: Optional[int] = None
    source_description: Optional[str] = None
    actual_schema: Optional[list[SchemaColumn]] = None
    reason: Optional[str] = None  # for skipped


class ProblemDataset(BaseModel):
    description: str
    inferred_columns: Optional[InferredColumns] = None
    user_confirmed_columns: Optional[dict[str, Any]] = None
    min_rows: int = 100
    source: Optional[DatasetSource] = None


# ---------------------------------------------------------------------------
# ML sub-problem
# ---------------------------------------------------------------------------

class MLProblem(BaseModel):
    id: str
    name: str
    description: str
    category: ProblemCategory
    engine: ExperimentEngine
    autogluon_task_type: Optional[AutoGluonTaskType] = None
    autorag_task_type: Optional[AutoRAGTaskType] = None
    hypothesis_evidence: list[str] = Field(default_factory=list)
    business_kpis: list[str] = Field(default_factory=list)
    dataset: Optional[ProblemDataset] = None


# ---------------------------------------------------------------------------
# Constraint summary
# ---------------------------------------------------------------------------

class DroppedProblem(BaseModel):
    name: str
    reason: str


class ConstraintSummary(BaseModel):
    narrative: str
    dropped_problems: list[DroppedProblem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Final output (consumed by experiment engines)
# ---------------------------------------------------------------------------

class FinalOutput(BaseModel):
    session_id: str
    status: str = "ready_for_experiments"
    business_problem: str
    domain: str
    constraint_summary: ConstraintSummary
    ml_problems: list[MLProblem]
    session_cost_usd: float = 0.0
    ready_for_experiments: bool = True


# ---------------------------------------------------------------------------
# API request/response
# ---------------------------------------------------------------------------

class StartConversationRequest(BaseModel):
    message: str = Field(..., description="Initial business problem description")
    session_id: Optional[str] = None


class RespondRequest(BaseModel):
    answers: Optional[dict[str, Any]] = None
    confirmed: Optional[bool] = None
    choice: Optional[str] = None
    prob_id: Optional[str] = None
    query: Optional[str] = None
    approved: Optional[bool] = None
    column_overrides: Optional[dict[str, Any]] = None
    adjustments: Optional[list[dict]] = None


class InterruptPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: InterruptType
    message: str
    data: Optional[dict[str, Any]] = None
    options: Optional[list[Any]] = None
    estimated_cost_usd: Optional[float] = None
    questions: Optional[list[str]] = None


class ConversationMessage(BaseModel):
    role: Literal["user", "agent"]
    agent_name: Optional[str] = None
    content: str
    timestamp: str
    card_type: Optional[str] = None
    card_data: Optional[dict[str, Any]] = None


class ConversationStateResponse(BaseModel):
    session_id: str
    status: ConversationStatus
    messages: list[ConversationMessage] = Field(default_factory=list)
    interrupt: Optional[InterruptPayload] = None
    final_output: Optional[dict[str, Any]] = None
    ml_problems_preview: Optional[list[dict]] = None
    pending_prob_id: Optional[str] = None
    session_cost_usd: float = 0.0


class UploadDatasetResponse(BaseModel):
    session_id: str
    prob_id: str
    s3_path: str
    message: str
