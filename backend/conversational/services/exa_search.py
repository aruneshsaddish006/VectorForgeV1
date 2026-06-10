"""Exa dataset discovery service.

Searches for public datasets on Kaggle, Hugging Face, and Google Dataset
Search using the Exa neural search API.

Env vars (loaded from .env via config.get_settings()):
    EXA_API_KEY — Exa API key
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from conversational.config import get_settings

logger = logging.getLogger(__name__)

_EXA_SEARCH_URL = "https://api.exa.ai/search"

_DATASET_DOMAINS = [
    "kaggle.com",
    "huggingface.co",
    "datasetsearch.research.google.com",
    "archive.ics.uci.edu",
    "data.gov",
    "github.com",
    "zenodo.org",
]


def build_dataset_search_query(
    problem_name: str,
    dataset_description: str,
    required_columns: list[str] | None = None,
) -> str:
    """Build a focused Exa search query for dataset discovery."""
    parts = [problem_name, dataset_description]
    if required_columns:
        cols = " ".join(required_columns[:5])
        parts.append(f"with columns: {cols}")
    return " ".join(parts)


async def search_datasets(
    query: str,
    num_results: int = 5,
) -> list[dict]:
    """Search for public datasets matching the query via Exa neural search.

    Args:
        query: Natural language description, e.g.
               "B2B SaaS churn dataset ARR NPS support tickets binary label".
        num_results: Max results to return.

    Returns:
        List of dicts, each with:
            title: str
            url: str
            description: str
            domain: str  (e.g. "kaggle.com")
            estimated_cost_usd: float
    """
    settings = get_settings()
    if not settings.exa_api_key:
        raise ValueError(
            "EXA_API_KEY is not set in .env. "
            "Add EXA_API_KEY=<your-key> to enable dataset discovery."
        )

    domain_clause = " OR ".join(f"site:{d}" for d in _DATASET_DOMAINS)
    full_query = f"{query} dataset CSV ({domain_clause})"

    logger.info("Exa search | query=%r num_results=%d", full_query, num_results)

    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "query": full_query,
        "num_results": num_results,
        "use_autoprompt": True,
        "type": "neural",
        "contents": {"text": {"maxCharacters": 500}},
    }

    async with httpx.AsyncClient(timeout=30, verify=settings.llm_ssl_verify) as client:
        resp = await client.post(_EXA_SEARCH_URL, json=payload, headers=headers)
        logger.info("Exa response | status=%d body_size=%d", resp.status_code, len(resp.content))
        resp.raise_for_status()
        data = resp.json()

    raw_results = data.get("results", [])
    logger.info("Exa returned %d raw results", len(raw_results))

    results = []
    for item in raw_results:
        url: str = item.get("url", "")
        description = (item.get("text") or item.get("snippet") or item.get("summary") or "")[:500]
        logger.debug("Exa result | title=%r url=%s description_len=%d", item.get("title"), url, len(description))
        results.append(
            {
                "title": item.get("title", "Untitled dataset"),
                "url": url,
                "description": description,
                "domain": _extract_domain(url),
                "estimated_cost_usd": 0.0,
            }
        )

    logger.info("Exa search complete | %d usable results", len(results))
    return results


async def search_use_case_benchmarks(
    problem_name: str,
    domain: str,
    num_results: int = 3,
) -> list[dict]:
    """Search for ROI / impact benchmarks for an ML use case.

    Returns short evidence snippets (title, url, snippet) or an empty list
    when EXA_API_KEY is missing or the request fails.
    """
    settings = get_settings()
    if not settings.exa_api_key:
        return []

    query = f"{problem_name} {domain} machine learning ROI impact results case study"

    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "num_results": num_results,
        "use_autoprompt": True,
        "type": "neural",
        "contents": {"text": {"maxCharacters": 400}},
    }

    try:
        async with httpx.AsyncClient(timeout=15, verify=settings.llm_ssl_verify) as client:
            resp = await client.post(_EXA_SEARCH_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": (item.get("text") or "")[:400],
        }
        for item in data.get("results", [])
        if item.get("url")
    ]


async def search_industry_discovery(
    business_problem: str,
    domain: str,
    num_results: int = 4,
) -> list[dict]:
    """Search for revenue impact, AI adoption trends, and workflow optimization stats.

    Runs three targeted Exa queries and aggregates results.
    Returns an empty list when EXA_API_KEY is missing or all requests fail.
    """
    settings = get_settings()
    if not settings.exa_api_key:
        return []

    queries = [
        f"{domain} {business_problem} revenue impact cost savings statistics 2024 2025",
        f"{domain} industry AI machine learning ROI adoption benchmark report",
        f"{business_problem} workflow automation optimization improvement percentage",
    ]

    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }

    all_results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20, verify=settings.llm_ssl_verify) as client:
            for query in queries:
                payload = {
                    "query": query,
                    "num_results": num_results,
                    "use_autoprompt": True,
                    "type": "neural",
                    "contents": {"text": {"maxCharacters": 600}},
                }
                try:
                    resp = await client.post(_EXA_SEARCH_URL, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            if item.get("url"):
                                all_results.append(
                                    {
                                        "title": item.get("title", ""),
                                        "url": item.get("url", ""),
                                        "snippet": (item.get("text") or "")[:600],
                                        "query_context": query,
                                    }
                                )
                except Exception:
                    continue
    except Exception:
        pass

    logger.info(
        "Exa industry discovery | domain=%r problem=%r results=%d",
        domain, business_problem, len(all_results),
    )
    return all_results


async def estimate_build_cost() -> float:
    """Return standard estimate for building a labelled dataset via Exa (~$0.10)."""
    return 0.10


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "unknown"
