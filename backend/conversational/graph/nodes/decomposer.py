"""Decomposer node — break down business problem into ML sub-problems.

Applies three analytical passes in one LLM call:
1. Constraint audit — what data/infrastructure exists?
2. Dual-lens scoping — business lens + DS lens alignment
3. ML routing — maps to AutoGluon task type or AutoRAG task type

Infers target/label/timestamp columns per task type from the problem description.

Interrupt type: "sub_problem_confirmation"
Resume payload:  {"confirmed": true, "column_overrides": {"prob_1": {"label_column": "is_churn"}}}
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml
from langgraph.types import interrupt

from conversational.graph.state import ConversationalState, agent_message
from conversational.models.schemas import InterruptType
from conversational.services.exa_search import search_use_case_benchmarks
from conversational.services.llm import structured_llm_call

_TAXONOMY_PATH = Path(__file__).parent.parent.parent / "models" / "problem_taxonomy.yaml"
_taxonomy_cache: dict | None = None


def _load_taxonomy() -> dict:
    global _taxonomy_cache
    if _taxonomy_cache is None:
        with open(_TAXONOMY_PATH) as f:
            _taxonomy_cache = yaml.safe_load(f)
    return _taxonomy_cache


def _taxonomy_summary() -> str:
    tax = _load_taxonomy()
    lines = ["SUPPORTED PROBLEM TYPES", "", "TRADITIONAL (engine: autogluon):"]
    for item in tax.get("traditional", []):
        lines.append(
            f"  {item['id']}: {item['description'][:100]}"
            f" | autogluon_task_type={item.get('autogluon_task_type')}"
            f" | predictor={item.get('predictor_class', '').split('.')[-1]}"
            f" | keywords: {', '.join(item.get('keywords', [])[:4])}"
        )
    lines += ["", "GENAI (engine: autorag):"]
    for item in tax.get("genai", []):
        lines.append(
            f"  {item['id']}: {item['description'][:100]}"
            f" | autorag_task_type={item.get('autorag_task_type')}"
            f" | keywords: {', '.join(item.get('keywords', [])[:4])}"
        )
    return "\n".join(lines)


_SYSTEM_TEMPLATE = """You are VectorForge's Strategy Agent.

Decompose the user's business problem into ML sub-problems that AutoGluon or
AutoRAG can solve. Apply three passes:

PASS 1 — CONSTRAINT AUDIT
What data is available? Labels? Infrastructure? Privacy? Drop any problem where
critical data is confirmed missing.

PASS 2 — DUAL-LENS SCOPING (both must pass)
  Business lens: Does the model output change a real decision? Who acts on it?
  DS lens:       Is there a ground-truth label? Are features available at prediction time?

PASS 3 — ML ROUTING (use only these types):
{taxonomy}

COLUMN INFERENCE RULES:
- binary_classification:        infer label_column (binary target)
- multiclass_classification:    infer label_column + class_labels[]
- regression:                   infer label_column (continuous numeric)
- time_series_forecasting:      infer target_column + timestamp_column + item_id_column
- text_classification:          infer text_column + label_column
- image_classification:         infer image_path_column + label_column
- ner:                          infer text_column + entity_annotations_column
- rag_question_answering:       infer corpus doc_id/contents + qa qid/query/retrieval_gt/generation_gt
- rag_document_retrieval:       infer corpus doc_id/contents + queries qid/query/retrieval_gt

Output 1–4 sub-problems maximum. The constraint_narrative must be a complete
paragraph a downstream orchestrator can use directly."""


_DECOMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "constraint_narrative": {
            "type": "string",
            "description": "Full paragraph: available data, missing data, infra, dropped problems with reasons",
        },
        "dropped_problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["name", "reason"],
            },
        },
        "ml_sub_problems": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string", "enum": ["traditional", "genai"]},
                    "engine": {"type": "string", "enum": ["autogluon", "autorag"]},
                    "taxonomy_id": {"type": "string"},
                    "autogluon_task_type": {"type": ["string", "null"]},
                    "autogluon_predictor_class": {"type": ["string", "null"]},
                    "autorag_task_type": {"type": ["string", "null"]},
                    "hypothesis_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "business_kpis": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "inferred_columns": {
                        "type": "object",
                        "description": "Keys vary by task type. Each value: {inferred_name, type, confidence, reason}",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "inferred_name": {"type": "string"},
                                "type": {"type": "string"},
                                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                "reason": {"type": "string"},
                            },
                        },
                    },
                    "dataset_description": {"type": "string"},
                    "min_rows": {"type": "integer"},
                },
                "required": [
                    "id", "name", "description", "category", "engine",
                    "taxonomy_id", "hypothesis_evidence", "business_kpis",
                    "inferred_columns", "dataset_description", "min_rows",
                ],
            },
        },
        "agent_summary": {"type": "string"},
        "projected_roi_summary": {"type": "string"},
    },
    "required": ["constraint_narrative", "dropped_problems", "ml_sub_problems", "agent_summary"],
}


async def decomposer_node(state: ConversationalState) -> dict:
    """Decompose business problem into ML sub-problems; interrupt for user confirmation."""
    system_prompt = _SYSTEM_TEMPLATE.format(taxonomy=_taxonomy_summary())
    user_context = _build_context(state)

    result = await structured_llm_call(
        system_prompt=system_prompt,
        user_message=user_context,
        tool_name="decompose_business_problem",
        tool_description="Decompose a business problem into ML sub-problems with routing and column inference",
        output_schema=_DECOMPOSE_SCHEMA,
    )

    ml_problems = result.get("ml_sub_problems", [])
    for prob in ml_problems:
        _enrich_from_taxonomy(prob)

    domain: str = state.get("domain") or "general"
    exa_insights = await _fetch_exa_insights(ml_problems, domain)

    constraint_summary = {
        "narrative": result.get("constraint_narrative", ""),
        "dropped_problems": result.get("dropped_problems", []),
    }

    card_data = {
        "use_cases_mapped": len(ml_problems),
        "projected_roi": result.get("projected_roi_summary", ""),
        "ml_problems": [
            {
                "id": p["id"],
                "name": p["name"],
                "engine": p["engine"],
                "category": p["category"],
                "autogluon_task_type": p.get("autogluon_task_type"),
                "autorag_task_type": p.get("autorag_task_type"),
                "business_kpis": p.get("business_kpis", []),
            }
            for p in ml_problems
        ],
        "constraint_summary": constraint_summary,
        "exa_insights": exa_insights,
    }

    state_update = {
        "status": "dataset_sourcing",
        "constraint_summary": constraint_summary,
        "ml_sub_problems": ml_problems,
        "messages": [
            agent_message(
                content=result.get("agent_summary", "Here is my analysis."),
                agent_name="Strategy Agent",
                card_type="strategy",
                card_data=card_data,
            )
        ],
    }

    interrupt(
        {
            "type": InterruptType.SUB_PROBLEM_CONFIRMATION,
            "message": result.get("agent_summary", "Here are the ML sub-problems I identified."),
            "data": card_data,
            "options": ["confirm", "adjust"],
        }
    )

    return state_update


def _build_context(state: ConversationalState) -> str:
    parts = [
        f"BUSINESS PROBLEM: {state.get('business_problem', 'Not specified')}",
        f"DOMAIN: {state.get('domain', 'Not specified')}",
        f"SCALE: {state.get('scale_description', 'Not specified')}",
        f"KNOWN CONSTRAINTS: {state.get('known_constraints', 'None specified')}",
    ]
    user_answers = [
        m["content"] for m in state.get("messages", []) if m.get("role") == "user"
    ]
    if user_answers:
        parts.append("\nUSER CONTEXT (from conversation):")
        parts.extend(f"  {msg}" for msg in user_answers[-4:])
    return "\n".join(parts)


async def _fetch_exa_insights(ml_problems: list[dict], domain: str) -> dict[str, list[dict]]:
    """Run Exa benchmark searches for all problems in parallel; gracefully skip failures."""
    async def _one(p: dict) -> tuple[str, list[dict]]:
        try:
            results = await search_use_case_benchmarks(p["name"], domain)
        except Exception:
            results = []
        return p["id"], results

    pairs = await asyncio.gather(*[_one(p) for p in ml_problems], return_exceptions=True)
    return {
        prob_id: insights
        for item in pairs
        if isinstance(item, tuple)
        for prob_id, insights in [item]
    }


def _enrich_from_taxonomy(problem: dict) -> None:
    """Fill in predictor_class and default min_rows from the taxonomy."""
    tax = _load_taxonomy()
    tax_id = problem.get("taxonomy_id", "")
    all_items = tax.get("traditional", []) + tax.get("genai", [])
    match = next((t for t in all_items if t["id"] == tax_id), None)
    if not match:
        return
    if not problem.get("autogluon_predictor_class"):
        problem["autogluon_predictor_class"] = match.get("predictor_class")
    if not problem.get("min_rows"):
        problem["min_rows"] = match.get("min_rows", 100)
