"""LangGraph state schema for the VectorForge conversational workflow.

ConversationalState is the single source of truth for the entire graph run.
Large blobs stay in S3; state stores only paths, summaries, and structured dicts.

Fields annotated with `operator.add` are append-only (messages, dataset_sources,
errors) — LangGraph merges them automatically across parallel branches.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Optional
from typing_extensions import TypedDict


class ConversationalState(TypedDict):
    # -------------------------------------------------------------------
    # Session metadata
    # -------------------------------------------------------------------
    session_id: str
    status: str          # ConversationStatus enum value as string

    # -------------------------------------------------------------------
    # Conversation history — append-only across all graph turns
    # Each entry: {role, content, agent_name, timestamp, card_type, card_data}
    # -------------------------------------------------------------------
    messages: Annotated[list[dict], operator.add]

    # -------------------------------------------------------------------
    # Stage 1 — Intake
    # Populated during the multi-turn intake clarification loop.
    # -------------------------------------------------------------------
    business_problem: Optional[str]
    domain: Optional[str]
    scale_description: Optional[str]
    known_constraints: Optional[str]
    clarification_questions_asked: int   # guard: max 3 clarification rounds

    # -------------------------------------------------------------------
    # Stage 2 — Decomposition
    # Produced by decomposer_node after dual-lens scoping, constraint audit,
    # hypothesis generation, and ML problem routing.
    # -------------------------------------------------------------------
    constraint_summary: Optional[dict]       # {narrative: str, dropped_problems: []}
    aligned_problems: Optional[list[dict]]  # problems passing dual-lens filter
    ml_sub_problems: Optional[list[dict]]   # full MLProblem dicts (one per ML task)

    # -------------------------------------------------------------------
    # Stage 3 — Dataset sourcing (sequential loop per sub-problem)
    # pending_dataset_index: which sub-problem we're currently sourcing
    # dataset_sources: accumulated source info per completed sub-problem
    # dataset_phase: current interrupt phase for the active problem
    #   ("choice" | "upload" | "discover" | "schema")
    # dataset_pending_s3_path: s3_path stored between upload and schema phases
    # -------------------------------------------------------------------
    pending_dataset_index: int
    dataset_sources: Annotated[list[dict], operator.add]
    dataset_phase: str           # tracks current interrupt phase
    dataset_pending_s3_path: str # persists s3_path across node re-runs

    # -------------------------------------------------------------------
    # Stage 4 — Final output
    # -------------------------------------------------------------------
    final_output: Optional[dict]    # FinalOutput model serialised to dict
    session_cost_usd: float

    # -------------------------------------------------------------------
    # Error tracking — append-only
    # -------------------------------------------------------------------
    errors: Annotated[list[str], operator.add]


def initial_state(session_id: str, first_message: str) -> ConversationalState:
    """Build the initial ConversationalState for a new conversation."""
    return ConversationalState(
        session_id=session_id,
        status="intake",
        messages=[
            {
                "role": "user",
                "content": first_message,
                "agent_name": None,
                "timestamp": _utcnow(),
                "card_type": None,
                "card_data": None,
            }
        ],
        business_problem=None,
        domain=None,
        scale_description=None,
        known_constraints=None,
        clarification_questions_asked=0,
        constraint_summary=None,
        aligned_problems=None,
        ml_sub_problems=None,
        pending_dataset_index=0,
        dataset_sources=[],
        dataset_phase="choice",
        dataset_pending_s3_path="",
        final_output=None,
        session_cost_usd=0.0,
        errors=[],
    )


def agent_message(
    content: str,
    agent_name: str,
    card_type: str | None = None,
    card_data: dict | None = None,
) -> dict:
    """Build a single agent message dict for appending to state.messages."""
    return {
        "role": "agent",
        "content": content,
        "agent_name": agent_name,
        "timestamp": _utcnow(),
        "card_type": card_type,
        "card_data": card_data,
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
