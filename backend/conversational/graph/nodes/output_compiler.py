"""Output compiler node — assemble FinalOutput and interrupt for user review.

Merges ml_sub_problems + dataset_sources into the mandatory structured output
that downstream orchestrators use to kick off AutoGluon and AutoRAG experiments.

Interrupt type: "final_review"
Resume payload: {"confirmed": true}  or  {"regenerate": true}
"""

from __future__ import annotations

import json
import logging

from langgraph.types import interrupt

from conversational.graph.state import ConversationalState, agent_message
from conversational.models.schemas import InterruptType

logger = logging.getLogger(__name__)


async def output_compiler_node(state: ConversationalState) -> dict:
    """Build final structured output; interrupt for user sign-off."""
    ml_problems: list[dict] = state.get("ml_sub_problems") or []
    dataset_sources: list[dict] = state.get("dataset_sources") or []
    constraint_summary: dict = state.get("constraint_summary") or {}

    sources_by_prob: dict[str, dict] = {
        s["problem_id"]: s for s in dataset_sources if s.get("problem_id")
    }

    experiments = [
        _build_experiment(prob, sources_by_prob.get(prob.get("id", ""), {}))
        for prob in ml_problems
    ]

    final_output = {
        "business_problem": state.get("business_problem", ""),
        "domain": state.get("domain", ""),
        "constraint_summary": constraint_summary.get("narrative", ""),
        "ml_problems": experiments,
        "session_cost_usd": state.get("session_cost_usd", 0.0),
        "ready_for_experiments": True,
        "max_experiment_per_round": 3,
        "num_round": 3,
    }

    logger.info(
        "[output_compiler] session=%s problems=%d schema:\n%s",
        state.get("session_id", "unknown"),
        len(experiments),
        json.dumps(final_output, indent=2, default=str),
    )

    review_resume = interrupt(
        {
            "type": InterruptType.FINAL_REVIEW.value,
            "message": (
                f"I've mapped **{len(experiments)} ML problem(s)** with dataset sources. "
                "Review the plan below and confirm to finalise, or ask me to adjust."
            ),
            "final_output": final_output,
            "options": ["confirm", "regenerate"],
        }
    )

    if (review_resume or {}).get("regenerate"):
        logger.info("[output_compiler] user requested regenerate — routing back to decomposer")
        return {"status": "decomposing"}

    logger.info(
        "[output_compiler] confirmed — writing final_output to state and Redis | session=%s",
        state.get("session_id", "unknown"),
    )
    return {
        "status": "complete",
        "final_output": final_output,
        "messages": [
            agent_message(
                content=(
                    f"Your VectorForge experiment plan is ready. "
                    f"{len(experiments)} ML problem(s) mapped with datasets. "
                    "Pass `final_output` to your orchestrator to kick off training."
                ),
                agent_name="Output Compiler",
                card_type="final_output",
                card_data=final_output,
            )
        ],
    }


def _build_experiment(problem: dict, source: dict) -> dict:
    """Build one entry in ml_problems matching conv-output-schema.json."""
    engine = problem.get("engine", "autogluon")
    return {
        "id": problem.get("id", ""),
        "name": problem.get("name", ""),
        "description": problem.get("description", ""),
        "category": problem.get("category", ""),
        "engine": engine,
        "autogluon_task_type": problem.get("autogluon_task_type"),
        "hypothesis_evidence": problem.get("hypothesis_evidence", []),
        "business_kpis": problem.get("business_kpis", []),
        "dataset": _build_dataset(problem, source, engine),
    }


def _build_dataset(problem: dict, source: dict, engine: str) -> dict:
    """Build dataset object matching conv-output-schema.json.

    AutoGluon: {description, target_column{inferred_name, type, reason}, source{s3_path, row_count}}
    AutoRAG:   {description, source{s3_path, row_count}}
    """
    description = problem.get("dataset_description", "")

    if engine == "autorag":
        return {
            "description": description,
            "source": _build_source(source),
        }

    # AutoGluon — extract the primary target column from inferred_columns
    inferred_columns: dict = problem.get("inferred_columns", {})
    column_mapping: dict = source.get("column_mapping", {})

    # Priority order for "the" target column across all AutoGluon task types
    target_key = next(
        (k for k in ("label_column", "target_column") if k in inferred_columns),
        next(iter(inferred_columns), None),
    )

    target_column: dict = {}
    if target_key:
        meta = inferred_columns[target_key]
        confirmed = column_mapping.get(target_key, {})
        target_column = {
            "inferred_name": confirmed.get("confirmed_name", meta.get("inferred_name", "")),
            "type": meta.get("type", ""),
            "reason": meta.get("reason", ""),
        }

    dataset: dict = {
        "description": description,
        "target_column": target_column,
        "source": _build_source(source),
    }

    # Include extra inferred columns for task types that need more than one
    # (e.g. timestamp_column + item_id_column for time series)
    extra = {
        k: {
            "inferred_name": column_mapping.get(k, {}).get(
                "confirmed_name", v.get("inferred_name", "")
            ),
            "type": v.get("type", ""),
        }
        for k, v in inferred_columns.items()
        if k != target_key
    }
    if extra:
        dataset["extra_columns"] = extra

    return dataset


def _build_source(source: dict) -> dict:
    """Map dataset_sourcing state to source{s3_path, row_count}.

    row_count is populated by the orchestrator after download; defaults to None
    here so the key is always present in the output for the consumer to fill.
    """
    result: dict = {
        "s3_path": source.get("s3_path", ""),
        "row_count": source.get("row_count"),
    }
    # If file hasn't been uploaded to S3 yet (discover path), keep the URL
    # so the orchestrator knows where to fetch it from.
    if not result["s3_path"] and source.get("dataset_url"):
        result["dataset_url"] = source["dataset_url"]

    return result
