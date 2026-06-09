"""Intake node — extract structured business problem context from natural language.

Interrupt type: "clarification"
Resume payload: {"answers": {"domain": "saas", "scale": "500/month"}}
"""

from __future__ import annotations

from langgraph.types import interrupt

from conversational.graph.state import ConversationalState, agent_message
from conversational.models.schemas import InterruptType
from conversational.services.llm import structured_llm_call

MAX_CLARIFICATION_ROUNDS = 3

_SYSTEM_PROMPT = """You are VectorForge's Intent Agent. Extract a structured
understanding of the user's business problem so it can be decomposed into ML
experiments.

Receive the full conversation and extract what is known. Identify what critical
information is still missing. Ask at most 3 focused questions at a time.
Be concise and business-oriented."""

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "business_problem": {
            "type": "string",
            "description": "Clear 1-3 sentence summary of the business problem",
        },
        "domain": {
            "type": "string",
            "description": "Industry: saas, fintech, ecommerce, healthcare, retail, logistics, other",
        },
        "scale_description": {
            "type": "string",
            "description": "Scale context: user count, transactions/day, revenue range, etc.",
        },
        "known_constraints": {
            "type": "string",
            "description": "Known constraints: latency, cost, data gaps, regulatory, infra limits",
        },
        "is_sufficient": {
            "type": "boolean",
            "description": "True if business_problem and domain are both present and unambiguous",
        },
        "missing_fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Field names that are missing or ambiguous",
        },
        "clarifying_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions to ask user. Empty if is_sufficient=true.",
        },
        "agent_summary": {
            "type": "string",
            "description": "1-2 sentence agent response to show before questions",
        },
    },
    "required": [
        "business_problem",
        "is_sufficient",
        "missing_fields",
        "clarifying_questions",
        "agent_summary",
    ],
}


async def intake_node(state: ConversationalState) -> dict:
    """Extract business problem; ask ONE clarification round then always advance.

    Flow matches test.md exactly:
      Step 1: user sends problem → LLM extracts → interrupt(clarification)
      Step 2: user answers       → skip re-evaluation, advance to decomposing
    """
    rounds = state.get("clarification_questions_asked", 0)

    # After the user has answered clarification questions, always advance.
    # Do NOT re-run the LLM — it will ask more questions and break the flow.
    if rounds >= MAX_CLARIFICATION_ROUNDS:
        return {
            "status": "decomposing",
            "clarification_questions_asked": rounds,
            "messages": [
                agent_message(
                    content="Got it — analysing your problem now.",
                    agent_name="Intent Agent",
                )
            ],
        }

    conversation_text = _format_messages(state["messages"])

    result = await structured_llm_call(
        system_prompt=_SYSTEM_PROMPT,
        user_message=conversation_text,
        tool_name="extract_business_problem",
        tool_description="Extract structured business problem context from the conversation",
        output_schema=_EXTRACTION_SCHEMA,
    )

    state_update: dict = {
        "status": "intake",
        "clarification_questions_asked": rounds,
    }

    # Merge extracted fields into state
    for field in ("business_problem", "domain", "scale_description", "known_constraints"):
        if result.get(field):
            state_update[field] = result[field]

    # If LLM already has enough context, skip straight to decomposing
    if result["is_sufficient"]:
        state_update["status"] = "decomposing"
        state_update["messages"] = [
            agent_message(
                content=result.get("agent_summary", "Got it. Analysing your problem now."),
                agent_name="Intent Agent",
                card_type="intake_summary",
                card_data={
                    "business_problem": result["business_problem"],
                    "domain": result.get("domain"),
                    "scale": result.get("scale_description"),
                },
            )
        ]
        return state_update

    # First (and only) clarification round
    state_update["clarification_questions_asked"] = rounds + 1
    state_update["messages"] = [
        agent_message(
            content=result.get("agent_summary", "A few quick questions:"),
            agent_name="Intent Agent",
            card_type="clarification",
            card_data={"questions": result["clarifying_questions"]},
        )
    ]

    interrupt(
        {
            "type": InterruptType.CLARIFICATION,
            "message": result.get("agent_summary", "A few quick questions:"),
            "questions": result["clarifying_questions"],
            "missing_fields": result.get("missing_fields", []),
        }
    )

    return state_update


def _format_messages(messages: list[dict]) -> str:
    return "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
        for m in messages
    )
