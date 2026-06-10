"""Discovery node — enrich intake with revenue impact and industry trend data.

Runs after intake, before decomposer. Uses Exa to find real-world stats on:
- Revenue impact of the identified business problem
- Industry AI/ML adoption rates and ROI benchmarks
- Workflow optimization improvements from automation

Emits a discovery_summary card then advances status to "decomposing".
Gracefully degrades when Exa is unavailable — still produces a card with
LLM-generated estimates so the user always sees a meaningful discovery step.
"""

from __future__ import annotations

from conversational.graph.state import ConversationalState, agent_message
from conversational.services.exa_search import search_industry_discovery
from conversational.services.llm import structured_llm_call

_SYNTHESIS_SYSTEM = """You are a business intelligence analyst specialising in AI/ML ROI.

Given Exa search results about a business domain and problem, extract concise,
high-impact statistics that demonstrate:
1. The revenue / cost burden of this problem today (quantified where possible)
2. The ROI companies achieve by applying AI/ML workflows to this problem
3. Industry AI adoption rates and benchmark improvement percentages

RULES:
- Prioritise specific numbers: percentages, dollar amounts, time savings
- If search results lack a specific number, use a plausible industry estimate
  and mark it with "(est.)" in the description
- Keep each stat label short (2-4 words), value concise ("$4.2M", "23%", "3.4x")
- chart_data should show 2-4 before/after comparisons as 0-100 index values
  (100 = worst/baseline, lower after = better)
- Return exactly 3-4 revenue_stats, 2-3 ai_workflow_stats, 2-3 trend_insights"""

_SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "revenue_impact_headline": {
            "type": "string",
            "description": "One compelling sentence about the revenue/cost stakes of this problem",
        },
        "revenue_stats": {
            "type": "array",
            "minItems": 3,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "description": {"type": "string"},
                    "tone": {
                        "type": "string",
                        "enum": ["default", "warning", "success", "primary"],
                    },
                },
                "required": ["label", "value", "description", "tone"],
            },
        },
        "industry_adoption": {
            "type": "object",
            "properties": {
                "adoption_pct": {
                    "type": "integer",
                    "description": "Percentage of companies in this industry using AI for this problem (0-100)",
                },
                "headline": {"type": "string"},
                "year": {"type": "string"},
            },
            "required": ["adoption_pct", "headline", "year"],
        },
        "ai_workflow_stats": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "value": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["metric", "value", "description"],
            },
        },
        "trend_insights": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "chart_data": {
            "type": "array",
            "description": "Before/after comparison (0-100 index, 100=worst baseline)",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "before": {"type": "integer", "minimum": 0, "maximum": 100},
                    "after": {"type": "integer", "minimum": 0, "maximum": 100},
                    "unit": {"type": "string", "description": "e.g. '% loss rate', 'hrs/week'"},
                },
                "required": ["label", "before", "after", "unit"],
            },
        },
    },
    "required": [
        "revenue_impact_headline",
        "revenue_stats",
        "industry_adoption",
        "ai_workflow_stats",
        "trend_insights",
        "chart_data",
    ],
}


async def discovery_node(state: ConversationalState) -> dict:
    """Enrich intake with Exa-sourced industry insights and revenue impact data."""
    business_problem = state.get("business_problem") or ""
    domain = state.get("domain") or "general"

    exa_results = await search_industry_discovery(business_problem, domain)

    context = _build_synthesis_context(business_problem, domain, exa_results)
    synthesis = await structured_llm_call(
        system_prompt=_SYNTHESIS_SYSTEM,
        user_message=context,
        tool_name="synthesize_discovery",
        tool_description="Synthesise revenue impact and industry trends from Exa search results",
        output_schema=_SYNTHESIS_SCHEMA,
    )

    card_data = {
        "business_problem": business_problem,
        "domain": domain,
        "revenue_impact_headline": synthesis.get("revenue_impact_headline", ""),
        "revenue_stats": synthesis.get("revenue_stats", []),
        "industry_adoption": synthesis.get("industry_adoption"),
        "ai_workflow_stats": synthesis.get("ai_workflow_stats", []),
        "trend_insights": synthesis.get("trend_insights", []),
        "chart_data": synthesis.get("chart_data", []),
        "exa_sources": [
            {"title": r["title"], "url": r["url"], "snippet": r["snippet"]}
            for r in exa_results[:5]
            if r.get("url")
        ],
    }

    return {
        "status": "decomposing",
        "messages": [
            agent_message(
                content=synthesis.get(
                    "revenue_impact_headline",
                    "Here is what industry data says about your problem.",
                ),
                agent_name="Discovery Agent",
                card_type="discovery_summary",
                card_data=card_data,
            )
        ],
    }


def _build_synthesis_context(
    business_problem: str,
    domain: str,
    exa_results: list[dict],
) -> str:
    parts = [
        f"BUSINESS PROBLEM: {business_problem}",
        f"DOMAIN: {domain}",
        "",
        "EXA SEARCH RESULTS:",
    ]
    for r in exa_results[:10]:
        parts.append(f"\n--- {r['title']} ({r['url']}) ---")
        parts.append(r["snippet"])
    if not exa_results:
        parts.append("(No Exa results available — generate industry estimates.)")
    return "\n".join(parts)
