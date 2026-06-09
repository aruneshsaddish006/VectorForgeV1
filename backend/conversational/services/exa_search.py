"""Exa dataset discovery service.

Searches for public datasets on Kaggle, Hugging Face, and Google Dataset
Search using the Exa neural search API.

Env vars (loaded from .env via config.get_settings()):
    EXA_API_KEY — Exa API key
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from conversational.config import get_settings

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

    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "query": full_query,
        "num_results": num_results,
        "use_autoprompt": True,
        "type": "neural",
    }

    async with httpx.AsyncClient(timeout=30, verify=settings.llm_ssl_verify) as client:
        resp = await client.post(_EXA_SEARCH_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", []):
        url: str = item.get("url", "")
        results.append(
            {
                "title": item.get("title", "Untitled dataset"),
                "url": url,
                "description": (item.get("text") or item.get("snippet", ""))[:500],
                "domain": _extract_domain(url),
                "estimated_cost_usd": 0.0,
            }
        )

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


async def estimate_build_cost() -> float:
    """Return standard estimate for building a labelled dataset via Exa (~$0.10)."""
    return 0.10


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "unknown"
