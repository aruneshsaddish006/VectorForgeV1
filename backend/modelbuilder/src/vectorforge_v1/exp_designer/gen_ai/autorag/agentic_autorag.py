#!/usr/bin/env python3
"""LangGraph agent for AutoRAG dataset creation and iterative OpenAI optimization.

The agent:
1. Profiles a folder of documents.
2. Uses an LLM to choose no-API-key parser/chunker strategies from AutoRAG-safe options.
3. Writes AutoRAG parse/chunk/RAG YAML configs.
4. Runs AutoRAG parsing/chunking.
5. Creates synthetic QA with AutoRAG's QA utilities.
6. Runs evidence-guided OpenAI RAG optimization rounds and reports measured best params.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import inspect
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import types
import uuid
from pathlib import Path
from typing import Any, TypedDict

import httpx
import pandas as pd
import yaml
from langgraph.graph import END, StateGraph
from openai import AsyncClient, OpenAI

from vectorforge_v1.utils.elasticache_pubsub import publish_experiment_result


def install_sentence_transformer_splitter_stub() -> None:
    module_name = "langchain_text_splitters.sentence_transformers"
    if module_name in sys.modules:
        return

    module = types.ModuleType(module_name)

    class SentenceTransformersTokenTextSplitter:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "SentenceTransformersTokenTextSplitter is disabled in VectorForge's non-GPU AutoRAG path. "
                "Use token, recursivecharacter, character, sentence, semantic_llama_index, "
                "semanticdoublemerging, sentencewindow, or simplefile chunking."
            )

    module.SentenceTransformersTokenTextSplitter = SentenceTransformersTokenTextSplitter
    sys.modules[module_name] = module


install_sentence_transformer_splitter_stub()

from autorag.chunker import Chunker
from autorag.data.qa.filter.dontknow import dontknow_filter_rule_based
from autorag.data.qa.generation_gt.openai_gen_gt import make_concise_gen_gt
from autorag.data.qa.query.openai_gen_query import factoid_query_gen
from autorag.data.qa.sample import random_single_hop
from autorag.data.qa.schema import Corpus, Raw
from autorag.evaluator import Evaluator
from autorag.parser import Parser
from vectorforge_v1.llm_gateway import (
    DEFAULT_AUTORAG_EMBEDDING_MODEL,
    OPENAI_API_BASE_URL,
    async_openai_direct_client,
    autorag_embedding_registry_key,
    normalize_openai_embedding_model,
    openai_direct_client,
    openai_embedding_model,
    require_openai_api_key,
)


PARSE_MODULE_CATALOG = [
    {"type": "pdf", "method": "pdfminer", "module_type": "langchain_parse", "api_key": False, "dependency": "pdfminer"},
    {"type": "pdf", "method": "pdfplumber", "module_type": "langchain_parse", "api_key": False, "dependency": "pdfplumber"},
    {"type": "pdf", "method": "pypdfium2", "module_type": "langchain_parse", "api_key": False, "dependency": "pypdfium2"},
    {"type": "pdf", "method": "pypdf", "module_type": "langchain_parse", "api_key": False, "dependency": "pypdf"},
    {"type": "pdf", "method": "pymupdf", "module_type": "langchain_parse", "api_key": False, "dependency": "fitz"},
    {"type": "pdf", "method": "unstructuredpdf", "module_type": "langchain_parse", "api_key": False, "dependency": "unstructured"},
    {"type": "ocr", "method": "naverclovaocr", "module_type": "clova", "api_key": True, "dependency": None},
    {"type": "ocr", "method": "llamaparse", "module_type": "llama_parse", "api_key": True, "dependency": None},
    {"type": "ocr", "method": "upstagedocumentparse", "module_type": "langchain_parse", "api_key": True, "dependency": "langchain_upstage"},
    {"type": "all", "method": "directory", "module_type": "langchain_parse", "api_key": False, "dependency": None},
    {"type": "all", "method": "unstructured", "module_type": "langchain_parse", "api_key": False, "dependency": "unstructured"},
    {"type": "csv", "method": "csv", "module_type": "langchain_parse", "api_key": False, "dependency": None},
    {"type": "json", "method": "json", "module_type": "langchain_parse", "api_key": False, "dependency": None},
    {"type": "md", "method": "unstructuredmarkdown", "module_type": "langchain_parse", "api_key": False, "dependency": "unstructured"},
    {"type": "html", "method": "bshtml", "module_type": "langchain_parse", "api_key": False, "dependency": "bs4"},
    {"type": "xml", "method": "unstructuredxml", "module_type": "langchain_parse", "api_key": False, "dependency": "unstructured"},
]

CHUNK_MODULE_CATALOG = [
    {
        "index": "token",
        "method": "token",
        "module_type": "llama_index_chunk",
        "language": "both",
        "base_model": "tiktoken",
        "api_key": False,
        "dependency": "tiktoken",
        "params": {"chunk_size": [512, 1024], "chunk_overlap": [64, 128]},
    },
    {
        "index": "token",
        "method": "sentencetransformerstoken",
        "module_type": "langchain_chunk",
        "language": "english",
        "base_model": "sentence-transformers/all-mpnet-base-v2",
        "api_key": False,
        "dependency": "sentence_transformers",
        "params": {"chunk_size": [512, 1024], "chunk_overlap": [64, 128]},
    },
    {
        "index": "character",
        "method": "character",
        "module_type": "langchain_chunk",
        "language": "both",
        "base_model": None,
        "api_key": False,
        "dependency": None,
        "params": {"chunk_size": [1200], "chunk_overlap": [150]},
    },
    {
        "index": "character",
        "method": "recursivecharacter",
        "module_type": "langchain_chunk",
        "language": "both",
        "base_model": None,
        "api_key": False,
        "dependency": None,
        "params": {"chunk_size": [1200, 1800], "chunk_overlap": [150, 250]},
    },
    {
        "index": "sentence",
        "method": "sentence",
        "module_type": "llama_index_chunk",
        "language": "both",
        "base_model": "tiktoken",
        "api_key": False,
        "dependency": "tiktoken",
        "params": {"chunk_size": [512, 1024], "chunk_overlap": [64, 128]},
    },
    {
        "index": "sentence",
        "method": "konlpy",
        "module_type": "langchain_chunk",
        "language": "korean",
        "base_model": "koNLPy",
        "api_key": False,
        "dependency": "konlpy",
        "params": {"chunk_size": [512], "chunk_overlap": [64]},
    },
    {
        "index": "semantic",
        "method": "semantic_llama_index",
        "module_type": "llama_index_chunk",
        "language": "english",
        "base_model": "nltk PunktSentenceTokenizer; embedding required",
        "api_key": False,
        "dependency": None,
        "requires_local_embedding": True,
        "params": {"sentence_splitter": ["nltk"], "embed_model": ["huggingface"]},
    },
    {
        "index": "semantic",
        "method": "semanticdoublemerging",
        "module_type": "llama_index_chunk",
        "language": "english",
        "base_model": "nltk Punkt",
        "api_key": False,
        "dependency": None,
        "params": {"sentence_splitter": ["nltk"]},
    },
    {
        "index": "window",
        "method": "sentencewindow",
        "module_type": "llama_index_chunk",
        "language": "english",
        "base_model": "nltk Punkt",
        "api_key": False,
        "dependency": None,
        "params": {"window_size": [3], "window_metadata_key": ["window"]},
    },
    {
        "index": "simple",
        "method": "simplefile",
        "module_type": "llama_index_chunk",
        "language": "both",
        "base_model": None,
        "api_key": False,
        "dependency": None,
        "params": {},
    },
]

NO_API_PARSE_OPTIONS = {
    file_type: [entry["method"] for entry in PARSE_MODULE_CATALOG if entry["type"] == file_type and not entry["api_key"]]
    for file_type in sorted({entry["type"] for entry in PARSE_MODULE_CATALOG if entry["type"] != "ocr"})
}

NO_API_CHUNK_OPTIONS = {
    "llama_index_chunk": {
        entry["method"]: entry["params"]
        for entry in CHUNK_MODULE_CATALOG
        if entry["module_type"] == "llama_index_chunk" and not entry["api_key"]
    },
    "langchain_chunk": {
        entry["method"]: entry["params"]
        for entry in CHUNK_MODULE_CATALOG
        if entry["module_type"] == "langchain_chunk" and not entry["api_key"]
    },
}

# AutoRAG runs entirely on the OpenAI API (OpenAI client + OPENAI_API_KEY).
DEFAULT_RAG_MODEL = "gpt-4o-mini-2024-07-18"
DEFAULT_EMBEDDING_MODEL = "openai_embed_3_small"
DEFAULT_GEVAL_MODEL = "gpt-4o-mini-2024-07-18"
DEFAULT_MAX_ROUNDS = 3
DEFAULT_ARCHITECTURES_PER_ROUND = 3
UNSUPPORTED_NON_GPU_CHUNK_METHODS = {
    "semantic_llama_index",
    "semanticdoublemerging",
    "sentencewindow",
}


def openai_client() -> OpenAI:
    return openai_direct_client(ssl_verify=False)


def async_openai_client() -> AsyncClient:
    return async_openai_direct_client(ssl_verify=False)


def normalize_openai_chat_model(model: str | None, default: str = DEFAULT_RAG_MODEL) -> str:
    """Return a model id that is valid for direct api.openai.com chat calls."""
    resolved = (model or "").strip() or default
    alias_map = {
        "openai/gpt-4o-mini": "gpt-4o-mini",
        "openai/gpt-4o-mini-2024-07-18": "gpt-4o-mini-2024-07-18",
    }
    if resolved in alias_map:
        return alias_map[resolved]
    if "/" in resolved:
        provider, bare_model = resolved.split("/", 1)
        if provider == "openai" and bare_model:
            return bare_model
        return default
    return resolved


def autorag_agent_model(default: str = DEFAULT_RAG_MODEL) -> str:
    # AutoRAG's QA, generator, and G-Eval calls use direct api.openai.com clients.
    return normalize_openai_chat_model(
        os.environ.get("AUTORAG_AGENT_MODEL")
        or os.environ.get("VECTORFORGE_AUTORAG_OPENAI_MODEL")
        or os.environ.get("AUTORAG_OPENAI_MODEL")
        or os.environ.get("VECTORFORGE_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL"),
        default,
    )


# AutoRAG's openai_llm generator validates the `llm:` value against MAX_TOKEN_DICT,
# which only contains plain OpenAI model names. Any provider-prefixed or unknown
# model (e.g. "anthropic/claude-sonnet-4.6", "gpt-oss-20b") must be mapped to a
# supported key or AutoRAG raises "None - 7" on the missing token limit.
AUTORAG_GENERATOR_FALLBACK_MODEL = "gpt-4o-mini"


def normalize_autorag_generator_model(model: str | None) -> str:
    from autorag.nodes.generator.openai_llm import MAX_TOKEN_DICT

    if model:
        if model in MAX_TOKEN_DICT:
            return model
        # strip a provider prefix like "openai/gpt-4o-mini" and retry
        bare = model.split("/", 1)[1] if "/" in model else model
        if bare in MAX_TOKEN_DICT:
            return bare
    return AUTORAG_GENERATOR_FALLBACK_MODEL


def autorag_geval_model() -> str:
    return normalize_openai_chat_model(
        os.environ.get("AUTORAG_AGENT_GEVAL_MODEL")
        or os.environ.get("VECTORFORGE_AUTORAG_GEVAL_OPENAI_MODEL")
        or os.environ.get("AUTORAG_GEVAL_OPENAI_MODEL"),
        autorag_agent_model(DEFAULT_GEVAL_MODEL),
    )


def autorag_embedding_model(default: str = DEFAULT_EMBEDDING_MODEL) -> str:
    # AutoRAG config validates embedding_model against its named registry keys
    # (openai_embed_3_small, ...), NOT raw OpenAI model strings. Emit the key here;
    # the actual API calls (patched OpenAIEmbedding) use the bare OpenAI name.
    return autorag_embedding_registry_key(
        openai_embedding_model(
            os.environ.get("AUTORAG_AGENT_EMBEDDING_MODEL")
            or os.environ.get("VECTORFORGE_AUTORAG_OPENAI_EMBEDDING_MODEL")
            or os.environ.get("AUTORAG_OPENAI_EMBEDDING_MODEL")
            or os.environ.get("VECTORFORGE_AUTORAG_EMBEDDING_MODEL")
            or os.environ.get("AUTORAG_EMBEDDING_MODEL"),
            default,
        )
    )


def configure_openai_environment() -> None:
    # AutoRAG runs entirely on the OpenAI API: generator, embeddings, and G-Eval
    # all use the OpenAI client with a real OPENAI_API_KEY.
    api_key = require_openai_api_key(context="AutoRAG designer")
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = OPENAI_API_BASE_URL
    os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE_URL


def _patch_embedding_resource(resource: Any) -> None:
    if getattr(resource, "_vectorforge_openai_embedding_patch", False):
        return

    original_create = resource.create

    # Embeddings go direct to OpenAI — use the bare OpenAI model name (no openai/ prefix).
    async def async_create(*args, **kwargs):
        if "model" in kwargs:
            kwargs["model"] = normalize_openai_embedding_model(kwargs["model"])
        return await original_create(*args, **kwargs)

    def sync_create(*args, **kwargs):
        if "model" in kwargs:
            kwargs["model"] = normalize_openai_embedding_model(kwargs["model"])
        return original_create(*args, **kwargs)

    resource.create = async_create if inspect.iscoroutinefunction(original_create) else sync_create
    resource._vectorforge_openai_embedding_patch = True


def patch_openai_clients_for_local_ssl() -> None:
    import openai

    configure_openai_environment()

    if getattr(openai, "_vectorforge_no_verify_patch", False):
        return

    original_openai = openai.OpenAI
    original_async_openai = openai.AsyncOpenAI

    class NoVerifyOpenAI(original_openai):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("api_key", require_openai_api_key(context="AutoRAG OpenAI client"))
            kwargs.setdefault("base_url", OPENAI_API_BASE_URL)
            if kwargs.get("http_client") is None:
                kwargs["http_client"] = httpx.Client(verify=False)
            super().__init__(*args, **kwargs)
            _patch_embedding_resource(self.embeddings)

    class NoVerifyAsyncOpenAI(original_async_openai):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("api_key", require_openai_api_key(context="AutoRAG async OpenAI client"))
            kwargs.setdefault("base_url", OPENAI_API_BASE_URL)
            if kwargs.get("http_client") is None:
                kwargs["http_client"] = httpx.AsyncClient(verify=False)
            super().__init__(*args, **kwargs)
            _patch_embedding_resource(self.embeddings)

    openai.OpenAI = NoVerifyOpenAI
    openai.AsyncOpenAI = NoVerifyAsyncOpenAI
    openai._vectorforge_no_verify_patch = True

    try:
        import autorag.nodes.generator.openai_llm as openai_llm

        openai_llm.AsyncOpenAI = NoVerifyAsyncOpenAI
    except Exception:
        pass

    try:
        import autorag.evaluation.metric.generation as generation_metric

        generation_metric.AsyncOpenAI = NoVerifyAsyncOpenAI
    except Exception:
        pass

    try:
        import llama_index.embeddings.openai.base as llama_openai_embedding

        llama_openai_embedding.OpenAI = NoVerifyOpenAI
        llama_openai_embedding.AsyncOpenAI = NoVerifyAsyncOpenAI
        if hasattr(llama_openai_embedding, "OpenAIEmbedding"):
            original_embedding = llama_openai_embedding.OpenAIEmbedding
            embedding_params = inspect.signature(original_embedding.__init__).parameters

            class DirectOpenAIEmbedding(original_embedding):
                def __init__(self, *args, **kwargs):
                    # Embeddings go direct to OpenAI with a real OPENAI_API_KEY.
                    kwargs["api_key"] = require_openai_api_key(context="AutoRAG OpenAI embedding client")
                    if "api_base" in embedding_params:
                        kwargs["api_base"] = OPENAI_API_BASE_URL
                    if "base_url" in embedding_params:
                        kwargs["base_url"] = OPENAI_API_BASE_URL
                    if "model" in embedding_params:
                        kwargs["model"] = normalize_openai_embedding_model(kwargs.get("model"))
                    if "model_name" in embedding_params:
                        kwargs["model_name"] = normalize_openai_embedding_model(kwargs.get("model_name"))
                    super().__init__(*args, **kwargs)

            llama_openai_embedding.OpenAIEmbedding = DirectOpenAIEmbedding
    except Exception:
        pass


SAFE_RAG_PIPELINE_CATALOG = [
    {
        "pipeline_type": "semantic_only",
        "nodes": ["optional_query_expansion", "semantic_retrieval", "prompt_maker", "generator"],
        "best_for": "baseline, balanced quality, lowest moving parts",
    },
    {
        "pipeline_type": "lexical_bm25",
        "nodes": ["optional_query_expansion", "lexical_retrieval", "prompt_maker", "generator"],
        "best_for": "keyword-heavy questions, exact terms, named methods, equations, and table labels",
    },
    {
        "pipeline_type": "hybrid_rrf",
        "nodes": ["optional_query_expansion", "semantic_retrieval", "lexical_retrieval", "hybrid_retrieval", "prompt_maker", "generator"],
        "best_for": "improving precision and recall by combining dense semantic matching with BM25 exact matching",
    },
]

SAFE_QUERY_EXPANSION_METHODS = ["none", "multi_query_expansion", "hyde", "query_decompose"]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "architecture"


def dependency_available(dependency: str | None) -> bool:
    if dependency == "sentence_transformers":
        return False
    return dependency is None or importlib.util.find_spec(dependency) is not None


def metric_name(metric: str | dict[str, Any]) -> str:
    if isinstance(metric, dict):
        return str(metric.get("metric_name", ""))
    return str(metric)


def g_eval_metric_for_goal(optimize_for: str) -> dict[str, Any]:
    goal = optimize_for.lower()
    dimensions = ["consistency", "relevance"]
    if any(token in goal for token in ["readable", "clarity", "clear", "flow", "coherent", "coherence"]):
        dimensions.append("coherence")
    if any(token in goal for token in ["fluent", "fluency", "natural", "polished"]):
        dimensions.append("fluency")
    if any(token in goal for token in ["overall", "balanced", "quality", "judge", "g-eval", "geval"]):
        dimensions = ["coherence", "consistency", "fluency", "relevance"]
    return {
        "metric_name": "g_eval",
        "metrics": list(dict.fromkeys(dimensions)),
        "model": autorag_geval_model(),
        "batch_size": int(os.environ.get("AUTORAG_AGENT_GEVAL_BATCH_SIZE", "4")),
    }


def rouge_metric() -> dict[str, str]:
    return {"metric_name": "rouge"}


def available_parse_catalog() -> list[dict[str, Any]]:
    return [
        {**entry, "available": dependency_available(entry.get("dependency"))}
        for entry in PARSE_MODULE_CATALOG
        if not entry["api_key"]
    ]


def available_chunk_catalog() -> list[dict[str, Any]]:
    return [
        {
            **entry,
            "available": (
                dependency_available(entry.get("dependency"))
                and entry["method"] not in UNSUPPORTED_NON_GPU_CHUNK_METHODS
            ),
        }
        for entry in CHUNK_MODULE_CATALOG
        if not entry["api_key"]
    ]


def parse_entry_for(file_type: str, parse_method: str) -> dict[str, Any] | None:
    for entry in PARSE_MODULE_CATALOG:
        if entry["type"] == file_type and entry["method"] == parse_method:
            return entry
    return None


def chunk_entry_for(module_type: str, chunk_method: str) -> dict[str, Any] | None:
    method = chunk_method.lower()
    for entry in CHUNK_MODULE_CATALOG:
        if entry["module_type"] == module_type and entry["method"] == method:
            return entry
    return None


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: str
    docs_dir: str
    work_dir: str
    document_description: str
    optimize_for: str
    qa_sample_count: int
    max_rounds: int
    architectures_per_round: int
    profile: dict[str, Any]
    plan: dict[str, Any]
    parse_config_path: str
    chunk_config_path: str
    rag_config_path: str
    raw_path: str
    corpus_path: str
    qa_path: str
    optimization_project_dir: str
    current_round: int
    experiment_plan: dict[str, Any]
    experiment_history: list[dict[str, Any]]
    architecture_rationale_paths: list[str]
    eval_results_paths: list[str]
    report_path: str
    errors: list[str]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def make_run_id() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"


def resolve_run_dir(work_dir_arg: str, fresh: bool) -> tuple[str, Path]:
    output_path = Path(work_dir_arg).resolve()
    if output_path.name.startswith("run_"):
        run_dir = output_path
        run_id = output_path.name
        if fresh:
            clean_dir(run_dir)
        else:
            run_dir.mkdir(parents=True, exist_ok=True)
        return run_id, run_dir

    output_path.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()
    run_dir = output_path / run_id
    if fresh:
        clean_dir(run_dir)
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def path_for_report(path: str | Path) -> str:
    path = Path(path).resolve()
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_subdirs(work_dir: Path) -> dict[str, Path]:
    return {
        "input": work_dir / "input",
        "planning": work_dir / "planning",
        "experiments": work_dir / "experiments",
        "reports": work_dir / "reports",
    }


def metric_decision_payload(state: AgentState, profile: dict[str, Any]) -> dict[str, Any]:
    metrics = metrics_for_goal(state["optimize_for"])
    primary = metrics["primary_metric"]
    metric_candidates = [
        {
            "metric": "retrieval_recall",
            "reason": "Measures whether the retrieved context includes the expected source passages.",
        },
        {
            "metric": "retrieval_precision",
            "reason": "Measures how much retrieved context is relevant, which helps reduce distracting evidence and hallucination risk.",
        },
        {
            "metric": "retrieval_f1",
            "reason": "Balances retrieval recall and precision for goals that need coverage without too much irrelevant context.",
        },
        {
            "metric": "rouge",
            "reason": "Checks generated answer overlap with the synthetic reference answer.",
        },
        {
            "metric": "g_eval",
            "reason": "Uses an OpenAI LLM judge for generation quality dimensions such as consistency and relevance.",
        },
    ]
    secondary = [metric for metric in ["retrieval_recall", "retrieval_precision", "retrieval_f1", "rouge", "g_eval"] if metric != primary]
    return {
        "task_type": "rag_optimization",
        "profile": metrics["prompt_style"],
        "selected_primary_metric": primary,
        "secondary_metrics": secondary,
        "metric_candidates": metric_candidates,
        "reasoning": (
            f"The user goal is '{state['optimize_for']}'. VectorForge maps this to "
            f"{primary} as the run-level primary metric so every experiment is compared on the same basis. "
            "Secondary retrieval and generation metrics are still recorded to show tradeoffs."
        ),
        "document_profile_summary": {
            "docs_dir": profile["docs_dir"],
            "file_count": profile["file_count"],
            "extensions": profile["extensions"],
            "supported_extensions": profile["supported_extensions"],
            "human_document_description": profile.get("human_document_description", ""),
        },
    }


def inspect_documents(state: AgentState) -> AgentState:
    docs_dir = Path(state["docs_dir"]).resolve()
    work_dir = Path(state["work_dir"]).resolve()
    input_dir = run_subdirs(work_dir)["input"] / "documents"
    input_dir.mkdir(parents=True, exist_ok=True)
    files = [path for path in docs_dir.iterdir() if path.is_file() and not path.name.startswith(".")]
    by_ext: dict[str, int] = {}
    sizes: dict[str, int] = {}
    for path in files:
        ext = path.suffix.lower().lstrip(".")
        by_ext[ext] = by_ext.get(ext, 0) + 1
        sizes[path.name] = path.stat().st_size

    parse_catalog = available_parse_catalog()
    chunk_catalog = available_chunk_catalog()
    runnable_parse_by_ext: dict[str, list[str]] = {}
    for entry in parse_catalog:
        if entry["available"]:
            runnable_parse_by_ext.setdefault(entry["type"], []).append(entry["method"])

    supported_exts = sorted(set(by_ext) & set(runnable_parse_by_ext))
    if not supported_exts:
        raise ValueError(f"No supported document types found in {docs_dir}. Found: {sorted(by_ext)}")

    staged_files: list[str] = []
    for path in files:
        ext = path.suffix.lower().lstrip(".")
        if ext in supported_exts:
            staged_path = input_dir / path.name
            shutil.copy2(path, staged_path)
            staged_files.append(str(staged_path))

    profile = {
        "docs_dir": str(docs_dir),
        "human_document_description": state.get("document_description", ""),
        "input_dir": str(input_dir),
        "staged_files": staged_files,
        "file_count": len(files),
        "extensions": by_ext,
        "supported_extensions": supported_exts,
        "no_api_parse_catalog": parse_catalog,
        "no_api_chunk_catalog": chunk_catalog,
        "runnable_parse_by_extension": {
            ext: runnable_parse_by_ext.get(ext, []) for ext in supported_exts
        },
        "runnable_chunk_methods": [
            {
                "module_type": entry["module_type"],
                "chunk_method": entry["method"],
                "index": entry["index"],
                "language": entry["language"],
                "base_model": entry["base_model"],
                "params": entry["params"],
            }
            for entry in chunk_catalog
            if entry["available"] and not entry.get("requires_local_embedding", False)
        ],
        "sizes": sizes,
    }

    work_dir = Path(state["work_dir"]).resolve()
    dirs = run_subdirs(work_dir)
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    write_json(
        dirs["input"] / "user_request.json",
        {
            "run_id": state.get("run_id", work_dir.name),
            "docs_dir": str(docs_dir),
            "document_description": state.get("document_description", ""),
            "optimization_goal": state["optimize_for"],
            "rounds": state["max_rounds"],
            "architectures_per_round": state["architectures_per_round"],
        },
    )
    write_json(dirs["input"] / "dataset_profile.json", profile)
    write_json(dirs["planning"] / "metric_decision.json", metric_decision_payload(state, profile))

    return {
        **state,
        "profile": profile,
    }


def fallback_plan(profile: dict[str, Any]) -> dict[str, Any]:
    parse_modules = []
    for ext in profile["supported_extensions"]:
        methods = profile["runnable_parse_by_extension"][ext]
        method = methods[0]
        parse_modules.append(
            {
                "module_type": "langchain_parse",
                "file_type": ext,
                "parse_method": method,
            }
        )

    description = str(profile.get("human_document_description", "")).lower()
    if any(token in description for token in ["table", "tables", "image", "images", "figure", "figures", "diagram"]):
        chunk_method = {
            "module_type": "langchain_chunk",
            "chunk_method": "recursivecharacter",
            "chunk_size": 1200,
            "chunk_overlap": 200,
            "add_file_name": "en",
        }
        rationale = (
            "Defaulted to local parsing with recursive character chunking because the human description "
            "mentions visual/table-heavy documents where layout-adjacent text benefits from conservative overlap."
        )
    else:
        chunk_method = {
            "module_type": "llama_index_chunk",
            "chunk_method": "token",
            "chunk_size": 1024,
            "chunk_overlap": 128,
            "add_file_name": "en",
        }
        rationale = "Defaulted to fast local parsing and token chunking for a mixed technical document collection."

    chunk_modules = [
        {
            **chunk_method,
        }
    ]
    return {
        "rationale": rationale,
        "parse_modules": parse_modules,
        "chunk_modules": chunk_modules,
        "rag": {
            "top_k": [3, 5],
            "embedding_model": autorag_embedding_model(),
            "generator_model": autorag_agent_model(),
        },
    }


def metrics_for_goal(optimize_for: str) -> dict[str, Any]:
    goal = optimize_for.lower()
    retrieval_metrics = ["retrieval_recall", "retrieval_precision", "retrieval_f1"]
    generator_metrics: list[dict[str, Any]] = [rouge_metric(), g_eval_metric_for_goal(optimize_for)]
    primary_metric = "retrieval_f1"
    prompt_style = "grounded_concise"
    suggested_top_k = [3, 5]
    hallucination_goal = any(
        token in goal
        for token in [
            "hallucination",
            "hallucinations",
            "hallucinate",
            "made up",
            "make up",
            "unsupported",
            "faithful",
            "grounded",
            "trust",
            "factual",
            "cite",
            "citations",
        ]
    )
    coverage_goal = any(token in goal for token in ["recall", "coverage", "broad", "find", "missing", "miss", "complete", "comprehensive"])
    precision_goal = any(token in goal for token in ["precision", "noise", "focused", "exact", "irrelevant", "distracting"])
    generation_goal = any(token in goal for token in ["answer", "generation", "rouge", "quality", "concise", "readable", "clarity"])
    judge_goal = any(token in goal for token in ["coherence", "consistency", "fluency", "relevance", "llm judge", "llm-as-judge"])

    if hallucination_goal and coverage_goal:
        primary_metric = "retrieval_f1"
        prompt_style = "strict_grounding"
        suggested_top_k = [3, 4, 5]
    elif hallucination_goal:
        primary_metric = "retrieval_precision"
        prompt_style = "strict_grounding"
        suggested_top_k = [2, 3, 4]
    elif coverage_goal:
        primary_metric = "retrieval_recall"
        prompt_style = "evidence_first"
        suggested_top_k = [4, 5, 7]
    elif precision_goal:
        primary_metric = "retrieval_precision"
        prompt_style = "strict_grounding"
        suggested_top_k = [2, 3, 4]
    elif generation_goal:
        primary_metric = "rouge"
        prompt_style = "grounded_concise"
        suggested_top_k = [3, 4, 5]
    elif judge_goal:
        primary_metric = "g_eval"
        prompt_style = "strict_grounding"
        suggested_top_k = [2, 3, 4]
    elif any(token in goal for token in ["balanced", "overall", "f1"]):
        primary_metric = "retrieval_f1"

    return {
        "retrieval_metrics": retrieval_metrics,
        "generator_metrics": generator_metrics,
        "primary_metric": primary_metric,
        "prompt_style": prompt_style,
        "suggested_top_k": suggested_top_k,
    }


def call_planner_llm(profile: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
You are configuring AutoRAG for a document folder.

Choose only parser and chunker options that do not require API keys or external model APIs.
RAG optimization may use OpenAI for embeddings and generation.

Human description of document content:
{profile.get("human_document_description") or "(not provided)"}

Document profile:
{json.dumps(profile, indent=2)}

Allowed parser options by extension:
{json.dumps(profile["runnable_parse_by_extension"], indent=2)}

Runnable no-API chunker options:
{json.dumps(profile["runnable_chunk_methods"], indent=2)}

Full documented no-API parser catalog, including unavailable local dependencies:
{json.dumps(profile["no_api_parse_catalog"], indent=2)}

Full documented no-API chunker catalog, including unavailable local dependencies:
{json.dumps(profile["no_api_chunk_catalog"], indent=2)}

Return JSON with:
- rationale: string
- parse_modules: list of AutoRAG parser YAML module dicts
- chunk_modules: list of AutoRAG chunk YAML module dicts
- rag: object with top_k list, embedding_model, generator_model

Parser module dict example:
{{"module_type": "langchain_parse", "file_type": "pdf", "parse_method": "pdfminer"}}

Chunk module dict example:
{{"module_type": "llama_index_chunk", "chunk_method": "token", "chunk_size": 1024, "chunk_overlap": 128, "add_file_name": "en"}}

Keep it simple. Prefer 1 parser per file type and 1-2 chunk candidates.
Use the human content description to choose parsing and chunking strategies. For example, table/image-heavy PDFs often deserve robust PDF parsing and conservative overlapping chunks.
Only choose entries marked runnable/available. Do not choose OCR or API-key parser modules.
"""
    client = openai_client()
    response = client.responses.create(
        model=autorag_agent_model(),
        input=[
            {"role": "system", "content": "Return only valid JSON. Do not use parser/chunker API-key modules."},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def validate_plan(plan: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    supported = set(profile["supported_extensions"])
    parse_modules = plan.get("parse_modules", [])
    chunk_modules = plan.get("chunk_modules", [])
    if not parse_modules or not chunk_modules:
        raise ValueError("Plan must include parse_modules and chunk_modules")

    for module in parse_modules:
        if module.get("module_type") != "langchain_parse":
            raise ValueError(f"Unsupported parser module_type: {module}")
        file_type = module.get("file_type")
        parse_method = str(module.get("parse_method", "")).lower()
        entry = parse_entry_for(str(file_type), parse_method)
        if file_type not in supported:
            raise ValueError(f"Parser file_type not present in docs: {file_type}")
        if entry is None or entry["api_key"]:
            raise ValueError(f"Parser requires unsupported method or API key: {parse_method}")
        if not dependency_available(entry.get("dependency")):
            raise ValueError(f"Parser dependency is not installed for {parse_method}: {entry.get('dependency')}")

    for module in chunk_modules:
        module_type = module.get("module_type")
        chunk_method = str(module.get("chunk_method", "")).lower()
        entry = chunk_entry_for(str(module_type), chunk_method)
        if module_type not in NO_API_CHUNK_OPTIONS or entry is None:
            raise ValueError(f"Unsupported chunk module_type: {module_type}")
        if entry["api_key"]:
            raise ValueError(f"Unsupported/API chunk method: {chunk_method}")
        if chunk_method in UNSUPPORTED_NON_GPU_CHUNK_METHODS:
            raise ValueError(f"Chunk method is disabled for non-GPU AutoRAG runs: {chunk_method}")
        if not dependency_available(entry.get("dependency")):
            raise ValueError(f"Chunk dependency is not installed for {chunk_method}: {entry.get('dependency')}")
        if entry.get("requires_local_embedding") and "embed_model" not in module:
            raise ValueError(f"{chunk_method} requires a local no-API embed_model parameter")

    rag = plan.setdefault("rag", {})
    rag.setdefault("top_k", [3, 5])
    rag["embedding_model"] = autorag_embedding_model(rag.get("embedding_model"))
    rag["generator_model"] = normalize_openai_chat_model(rag.get("generator_model"), DEFAULT_RAG_MODEL)
    return plan


def normalize_plan(plan: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    normalized_parse_modules = []
    for module in plan.get("parse_modules", []):
        parse_method = str(module.get("parse_method") or module.get("method") or module.get("module") or "").lower()
        file_type = module.get("file_type") or module.get("type")
        if not file_type and parse_method:
            matching_exts = [
                ext
                for ext, methods in profile["runnable_parse_by_extension"].items()
                if parse_method in methods
            ]
            if len(matching_exts) == 1:
                file_type = matching_exts[0]
        normalized_parse_modules.append(
            {
                **module,
                "module_type": module.get("module_type", "langchain_parse"),
                "file_type": file_type,
                "parse_method": parse_method,
            }
        )

    normalized_chunk_modules = []
    for module in plan.get("chunk_modules", []):
        chunk_method = str(module.get("chunk_method") or module.get("method") or module.get("module") or "").lower()
        if chunk_method in UNSUPPORTED_NON_GPU_CHUNK_METHODS:
            continue
        module_type = module.get("module_type")
        if not module_type and chunk_method:
            matches = [
                entry["module_type"]
                for entry in profile["runnable_chunk_methods"]
                if entry["chunk_method"] == chunk_method
            ]
            if len(matches) == 1:
                module_type = matches[0]
        normalized_module = {
            **module,
            "module_type": module_type,
            "chunk_method": chunk_method,
        }
        if normalized_module.get("add_file_name") not in {None, "en", "ko", "ja"}:
            normalized_module["add_file_name"] = "en"
        normalized_chunk_modules.append(
            normalized_module
        )

    if not normalized_chunk_modules:
        runnable = profile.get("runnable_chunk_methods") or []
        preferred = next(
            (
                entry
                for entry in runnable
                if entry["chunk_method"] in {"recursivecharacter", "sentence", "token", "character", "simplefile"}
            ),
            runnable[0] if runnable else None,
        )
        if preferred:
            normalized_chunk_modules.append(
                {
                    "module_type": preferred["module_type"],
                    "chunk_method": preferred["chunk_method"],
                    "chunk_size": 1024,
                    "chunk_overlap": 128,
                    "add_file_name": "en",
                }
            )

    return {
        **plan,
        "parse_modules": normalized_parse_modules,
        "chunk_modules": normalized_chunk_modules,
    }


def plan_configs(state: AgentState) -> AgentState:
    profile = state["profile"]
    try:
        plan = validate_plan(normalize_plan(call_planner_llm(profile), profile), profile)
    except Exception as exc:
        plan = fallback_plan(profile)
        plan["rationale"] += f" Planner fallback reason: {exc}"
    return {**state, "plan": plan}


def architecture_fallback_plan(state: AgentState) -> dict[str, Any]:
    metrics = metrics_for_goal(state["optimize_for"])
    model = autorag_agent_model()
    top_k_values = metrics["suggested_top_k"]
    current_round = state.get("current_round", 1)
    previous_best = best_experiment_so_far(state.get("experiment_history", []))
    baseline_top_k = int(previous_best.get("top_k", top_k_values[0])) if previous_best else top_k_values[0]
    baseline_final_top_k = int(previous_best.get("final_top_k", min(baseline_top_k, 4))) if previous_best else top_k_values[0]
    baseline_pipeline = str(previous_best.get("pipeline_type", "semantic_only")) if previous_best else "semantic_only"
    primary_metric = metrics["primary_metric"]

    if current_round == 1:
        round_goal = "Fallback Round 1 baselines: compare simple semantic, broader semantic, and hybrid evidence retrieval."
        candidates = [
            ("baseline_semantic", "Round 1 baseline aligned to the human goal.", "semantic_only", top_k_values[0], top_k_values[0], "none", metrics["prompt_style"]),
            ("broader_semantic", "Round 1 recall probe to see whether more context improves the target metric.", "semantic_only", top_k_values[min(1, len(top_k_values) - 1)], top_k_values[min(1, len(top_k_values) - 1)], "multi_query_expansion", "evidence_first"),
            ("hybrid_precision_probe", "Round 1 hybrid probe to test whether dense and lexical agreement reduces unsupported answers.", "hybrid_rrf", top_k_values[min(2, len(top_k_values) - 1)], max(1, top_k_values[0]), "none", "strict_grounding"),
        ]
    else:
        round_goal = (
            f"Fallback Round {current_round} exploitation: eliminate weaker architecture families and "
            f"mutate the current best {baseline_pipeline} configuration for measured {primary_metric} improvement."
        )
        target_top_k = max(1, min(10, baseline_top_k - 1 if primary_metric == "retrieval_precision" else baseline_top_k + 1))
        candidates = [
            (
                "best_small_mutation",
                "Closest targeted refinement of the current best; this is designed as the strongest candidate.",
                baseline_pipeline,
                target_top_k,
                max(1, min(8, min(target_top_k, baseline_final_top_k))),
                "none" if primary_metric == "retrieval_precision" else "multi_query_expansion",
                metrics["prompt_style"],
            ),
            (
                "precision_variant",
                "Tighter context variant to reduce irrelevant evidence and unsupported generation.",
                baseline_pipeline,
                max(1, target_top_k - 1),
                max(1, min(8, baseline_final_top_k - 1)),
                "none",
                "strict_grounding",
            ),
            (
                "recall_variant",
                "Slightly wider context variant in case the current best is missing key evidence.",
                baseline_pipeline,
                min(10, target_top_k + 1),
                max(1, min(8, baseline_final_top_k + 1)),
                "multi_query_expansion",
                "evidence_first",
            ),
        ]

    selected = candidates[: max(1, state["architectures_per_round"])]
    while len(selected) < state["architectures_per_round"]:
        selected.append(candidates[len(selected) % len(candidates)])

    architectures = []
    for index, (name, reason, pipeline_type, top_k, final_top_k, query_expansion_method, prompt_style) in enumerate(selected, start=1):
        architectures.append(
            {
                "architecture_name": slugify(f"r{current_round}_exp{index}_{name}"),
                "reason": f"{reason} Human goal: {state['optimize_for']}.",
                "pipeline_type": pipeline_type,
                "query_expansion_method": query_expansion_method,
                "top_k": max(1, min(10, int(top_k))),
                "final_top_k": max(1, min(8, int(final_top_k), int(top_k))),
                "filter_threshold": 0.15,
                "reranker_type": "pass_reranker",
                "temperature": 0.0,
                "prompt_style": prompt_style,
                "retrieval_metrics": metrics["retrieval_metrics"],
                "generator_metrics": metrics["generator_metrics"],
                "primary_metric": metrics["primary_metric"],
                "embedding_model": autorag_embedding_model(),
                "generator_model": model,
            }
        )
    return {
        "round_goal": round_goal,
        "architectures": architectures,
    }


def call_architecture_planner_llm(state: AgentState, prior_rationale: str, prior_results: str) -> dict[str, Any]:
    profile = state["profile"]
    metrics = metrics_for_goal(state["optimize_for"])
    previous_best = best_experiment_so_far(state.get("experiment_history", []))
    prompt = f"""
You are planning AutoRAG optimization experiments.

Create exactly {state["architectures_per_round"]} simple, non-GPU RAG pipeline configurations for round {state["current_round"]}.
You are allowed to choose any pipeline from the safe non-GPU catalog below.
Use OpenAI embeddings and OpenAI LLM generation when model calls are needed.

Safe non-GPU pipeline catalog:
{json.dumps(SAFE_RAG_PIPELINE_CATALOG, indent=2)}

Optional query expansion methods:
{json.dumps(SAFE_QUERY_EXPANSION_METHODS, indent=2)}

Human optimization goal:
{state["optimize_for"]}

Human description of document content:
{state.get("document_description") or state["profile"].get("human_document_description") or "(not provided)"}

Use metrics aligned with the goal:
{json.dumps(metrics, indent=2)}

Document profile:
{json.dumps(profile, indent=2)}

Previous architecture rationale markdown:
{prior_rationale or "(none; this is the first round)"}

Previous evaluation results markdown:
{prior_results or "(none; this is the first round)"}

Best experiment so far:
{json.dumps(previous_best, indent=2, default=str) if previous_best else "(none; this is the first round)"}

Architecture elimination rule:
{f"Round {state['current_round']} must treat {previous_best.get('pipeline_type')} as the surviving baseline architecture. Generate only targeted mutations of that pipeline_type; do not re-test eliminated pipeline families unless the prior metrics show the surviving baseline cannot optimize the selected primary metric." if previous_best and state["current_round"] > 1 else "Round 1 should compare diverse baseline architecture families."}

Interpret non-technical goals yourself. Examples:
- "reduce hallucinations" means prefer strict grounding, retrieval_precision, lower top_k, and sometimes hybrid_rrf so dense and lexical retrieval agree on evidence.
- "do not miss anything important" means prefer retrieval_recall, broader top_k, and sometimes multi_query_expansion or hyde.
- "short accurate answers" means prefer grounded_concise prompts, low temperature, and balanced retrieval_f1/rouge.
- "LLM as judge", "coherence", "consistency", "fluency", or "relevance" means include g_eval and consider it as a primary generation metric when explicitly requested.
- "too much irrelevant context" means prefer retrieval_precision and smaller top_k.

Planning policy:
- Round 1: establish diverse baselines. Try meaningfully different safe pipelines and parameters.
- Round 2: eliminate weaker Round 1 architecture families. Use the best Round 1 pipeline_type as the baseline and make all candidates targeted mutations of that baseline.
- Round 3: continue exploiting the current best surviving architecture. Make all candidates targeted refinements intended to beat the current best score.
- Each new round must explain how it is expected to improve over prior results. Do not repeat the same architecture unless it was the best and you are making a deliberate small mutation.
- After Round 1, do not output one semantic_only, one lexical_bm25, and one hybrid_rrf just for coverage. That pattern is disallowed because poor architecture families should be eliminated.
- Prefer monotonic progress toward the primary metric. If a previous result has high recall but weak precision, reduce top_k, switch to hybrid_rrf, use lexical_bm25 for exact evidence, or use strict_grounding. If precision is high but recall is weak, increase top_k, switch to hybrid_rrf, or use evidence_first.
- Query expansion is optional. Use none for precision/hallucination-focused experiments unless recall is weak; use multi_query_expansion or hyde for recall/coverage experiments; use query_decompose for complex multi-part questions.
- Plan Round 3 as the best expected round. It should be an exploitation round: start from the current best measured configuration, then make small targeted changes that are likely to improve the primary metric.
- Keep the same primary_metric for every architecture in this run: {metrics["primary_metric"]}. Other metrics can be reported as secondary evidence, but final best selection must compare the same metric across experiments.
- Keep reported metric values honest. Never invent, smooth, or randomize evaluation scores; the measured AutoRAG results decide the winner.

Return JSON with:
- round_goal: string
- architectures: list of exactly {state["architectures_per_round"]} objects

Each architecture object must include:
- architecture_name: short unique snake_case name
- reason: why this config is worth testing for the human goal and document profile
- pipeline_type: one of semantic_only, lexical_bm25, hybrid_rrf
- query_expansion_method: one of none, multi_query_expansion, hyde, query_decompose
- top_k: integer from 1 to 10 for initial retrieval breadth
- final_top_k: integer from 1 to 8 for final prompt context
- filter_threshold: number from 0.05 to 0.45, keep for compatibility but it is ignored by current safe pipelines
- reranker_type: use pass_reranker for compatibility; this field is ignored by the current safe pipelines
- temperature: number from 0.0 to 0.3
- prompt_style: one of grounded_concise, evidence_first, strict_grounding
- retrieval_metrics: list, use only retrieval_recall, retrieval_precision, retrieval_f1
- generator_metrics: list of metric objects, include {json.dumps(rouge_metric())} and this exact G-Eval object when judge-style evaluation is useful: {json.dumps(g_eval_metric_for_goal(state["optimize_for"]))}
- primary_metric: one of retrieval_recall, retrieval_precision, retrieval_f1, rouge, g_eval
- embedding_model: use {autorag_embedding_model()}
- generator_model: use {autorag_agent_model()}

Do not add GPU modules, local model serving, external reranker APIs, passage_filter, passage_reranker, or unsupported stages.
"""
    client = openai_client()
    response = client.responses.create(
        model=autorag_agent_model(),
        input=[
            {"role": "system", "content": "Return only valid JSON for AutoRAG experiment planning."},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def normalize_architecture_plan(plan: dict[str, Any], state: AgentState) -> dict[str, Any]:
    metrics = metrics_for_goal(state["optimize_for"])
    previous_best = best_experiment_so_far(state.get("experiment_history", []))
    surviving_pipeline = (
        previous_best.get("pipeline_type")
        if previous_best and state.get("current_round", 1) > 1
        else None
    )
    architectures = []
    seen: set[str] = set()
    for index, arch in enumerate(plan.get("architectures", []), start=1):
        base_name = slugify(str(arch.get("architecture_name") or f"architecture_{index}"))
        if not base_name.startswith(f"r{state.get('current_round', 1)}_exp"):
            base_name = f"r{state.get('current_round', 1)}_exp{index}_{base_name}"
        name = base_name
        suffix = index
        while name in seen:
            name = f"{base_name}_{suffix}"
            suffix += 1
        seen.add(name)
        top_k = int(arch.get("top_k", 3))
        top_k = max(1, min(10, top_k))
        final_top_k = int(arch.get("final_top_k", min(top_k, 5)))
        final_top_k = max(1, min(8, final_top_k, top_k))
        filter_threshold = float(arch.get("filter_threshold", 0.2))
        filter_threshold = max(0.05, min(0.45, filter_threshold))
        temperature = float(arch.get("temperature", 0.0))
        temperature = max(0.0, min(0.3, temperature))
        pipeline_type = arch.get("pipeline_type", "semantic_only")
        if pipeline_type not in {entry["pipeline_type"] for entry in SAFE_RAG_PIPELINE_CATALOG}:
            pipeline_type = "semantic_only"
        if surviving_pipeline:
            pipeline_type = str(surviving_pipeline)
        query_expansion_method = arch.get("query_expansion_method", "none")
        if query_expansion_method not in SAFE_QUERY_EXPANSION_METHODS:
            query_expansion_method = "none"
        reranker_type = arch.get("reranker_type", "pass_reranker")
        if reranker_type not in {"pass_reranker", "rankgpt"}:
            reranker_type = "pass_reranker"
        retrieval_metrics = [
            metric
            for metric in arch.get("retrieval_metrics", metrics["retrieval_metrics"])
            if metric in {"retrieval_recall", "retrieval_precision", "retrieval_f1"}
        ] or metrics["retrieval_metrics"]
        generator_metrics = []
        for metric in arch.get("generator_metrics", metrics["generator_metrics"]):
            current_metric_name = metric_name(metric)
            if current_metric_name == "rouge":
                generator_metrics.append(rouge_metric())
            elif current_metric_name == "g_eval":
                generator_metrics.append(g_eval_metric_for_goal(state["optimize_for"]))
        if "rouge" not in [metric_name(metric) for metric in generator_metrics]:
            generator_metrics.insert(0, rouge_metric())
        if "g_eval" not in [metric_name(metric) for metric in generator_metrics]:
            generator_metrics.append(g_eval_metric_for_goal(state["optimize_for"]))
        primary_metric = metrics["primary_metric"]
        allowed_primary_metrics = set(retrieval_metrics + [metric_name(metric) for metric in generator_metrics])
        if primary_metric not in allowed_primary_metrics:
            primary_metric = metrics["primary_metric"]
        architectures.append(
            {
                "architecture_name": name,
                "reason": (
                    str(arch.get("reason") or "Simple non-GPU OpenAI RAG experiment.")
                    + (
                        f" This round applies elimination: weaker architecture families were dropped and this candidate mutates the surviving {pipeline_type} baseline."
                        if surviving_pipeline
                        else ""
                    )
                ),
                "pipeline_type": pipeline_type,
                "query_expansion_method": query_expansion_method,
                "top_k": top_k,
                "final_top_k": final_top_k,
                "filter_threshold": filter_threshold,
                "reranker_type": reranker_type,
                "temperature": temperature,
                "prompt_style": arch.get("prompt_style", "grounded_concise"),
                "retrieval_metrics": retrieval_metrics,
                "generator_metrics": generator_metrics,
                "primary_metric": primary_metric,
                "embedding_model": autorag_embedding_model(arch.get("embedding_model")),
                "generator_model": arch.get("generator_model", autorag_agent_model()),
            }
        )

    if len(architectures) != state["architectures_per_round"]:
        return architecture_fallback_plan(state)
    return {**plan, "architectures": architectures}


def read_markdown_history(paths: list[str]) -> str:
    chunks = []
    for path in paths:
        file_path = Path(path)
        if file_path.exists():
            chunks.append(f"# {file_path.name}\n{file_path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def best_experiment_so_far(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not history:
        return None
    scored = [item for item in history if item.get("primary_score") is not None]
    if not scored:
        return None
    return max(scored, key=lambda item: item["primary_score"])


def plan_experiment_round(state: AgentState) -> AgentState:
    current_round = state.get("current_round", 1)
    state = {
        **state,
        "current_round": current_round,
        "experiment_history": state.get("experiment_history", []),
        "architecture_rationale_paths": state.get("architecture_rationale_paths", []),
        "eval_results_paths": state.get("eval_results_paths", []),
    }
    prior_rationale = read_markdown_history(state["architecture_rationale_paths"])
    prior_results = read_markdown_history(state["eval_results_paths"])
    try:
        experiment_plan = normalize_architecture_plan(
            call_architecture_planner_llm(state, prior_rationale, prior_results),
            state,
        )
    except Exception as exc:
        experiment_plan = architecture_fallback_plan(state)
        experiment_plan["round_goal"] += f" Planner fallback reason: {exc}"
    return {**state, "experiment_plan": experiment_plan}


def prompt_for_style(style: str) -> str:
    prompts = {
        "evidence_first": (
            "First identify the most relevant retrieved evidence, then answer concisely. "
            "Use only the retrieved passages. If the answer is not present, say \"I don't know.\"\n\n"
            "Question:\n{query}\n\nRetrieved passages:\n{retrieved_contents}\n\nAnswer:\n"
        ),
        "strict_grounding": (
            "Answer strictly from the retrieved passages. Do not infer beyond the text. "
            "If the retrieved passages do not contain the answer, say \"I don't know.\"\n\n"
            "Question:\n{query}\n\nRetrieved passages:\n{retrieved_contents}\n\nAnswer:\n"
        ),
        "grounded_concise": (
            "Use only the retrieved passages to answer the question in a concise way. "
            "If the answer is not present, say \"I don't know.\"\n\n"
            "Question:\n{query}\n\nRetrieved passages:\n{retrieved_contents}\n\nAnswer:\n"
        ),
    }
    return prompts.get(style, prompts["grounded_concise"])


def build_rag_config(arch: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    collection = slugify(arch["architecture_name"])
    embedding_model = autorag_embedding_model(arch.get("embedding_model"))
    nodes = []

    if arch.get("query_expansion_method", "none") != "none":
        nodes.append(
            {
                "node_type": "query_expansion",
                "strategy": {
                    "metrics": arch["retrieval_metrics"],
                    "strategy": "mean",
                    "top_k": arch["top_k"],
                    "retrieval_modules": [
                        {
                            "module_type": "vectordb",
                            "vectordb": "openai_chroma",
                            "top_k": arch["top_k"],
                            "embedding_batch": 8,
                        }
                    ],
                },
                "modules": [
                    {
                        "module_type": arch["query_expansion_method"],
                        "generator_module_type": "openai_llm",
                        "llm": normalize_autorag_generator_model(arch["generator_model"]),
                        "batch": 4,
                        "temperature": 0.0,
                    }
                ],
            }
        )

    if arch["pipeline_type"] in {"semantic_only", "hybrid_rrf"}:
        nodes.append(
            {
                "node_type": "semantic_retrieval",
                "strategy": {
                    "metrics": arch["retrieval_metrics"],
                    "strategy": "mean",
                },
                "modules": [
                    {
                        "module_type": "vectordb",
                        "vectordb": "openai_chroma",
                        "top_k": arch["top_k"],
                        "embedding_batch": 8,
                    }
                ],
            }
        )

    if arch["pipeline_type"] in {"lexical_bm25", "hybrid_rrf"}:
        nodes.append(
            {
                "node_type": "lexical_retrieval",
                "strategy": {
                    "metrics": arch["retrieval_metrics"],
                    "strategy": "mean",
                },
                "modules": [
                    {
                        "module_type": "bm25",
                        "bm25_tokenizer": "porter_stemmer",
                        "top_k": arch["top_k"],
                    }
                ],
            }
        )

    if arch["pipeline_type"] == "hybrid_rrf":
        nodes.append(
            {
                "node_type": "hybrid_retrieval",
                "strategy": {
                    "metrics": arch["retrieval_metrics"],
                    "strategy": "normalize_mean",
                },
                "modules": [
                    {
                        "module_type": "hybrid_rrf",
                        "top_k": arch["final_top_k"],
                        "weight_range": [[10, 80]],
                    }
                ],
            }
        )

    nodes.extend(
        [
            {
                "node_type": "prompt_maker",
                "strategy": {"metrics": arch["generator_metrics"]},
                "modules": [
                    {
                        "module_type": "fstring",
                        "prompt": prompt_for_style(arch["prompt_style"]),
                    }
                ],
            },
            {
                "node_type": "generator",
                "strategy": {"metrics": arch["generator_metrics"], "strategy": "mean"},
                "modules": [
                    {
                        "module_type": "openai_llm",
                        "llm": normalize_autorag_generator_model(arch["generator_model"]),
                        "batch": 4,
                        "temperature": arch["temperature"],
                    }
                ],
            },
        ]
    )

    return {
        "vectordb": [
            {
                "name": "openai_chroma",
                "db_type": "chroma",
                "client_type": "persistent",
                "embedding_model": embedding_model,
                "collection_name": collection,
                "path": str(project_dir / "resources" / "chroma"),
                "similarity_metric": "cosine",
                "embedding_batch": 16,
            }
        ],
        "node_lines": [
            {
                "node_line_name": "agentic_openai_rag",
                "nodes": nodes,
            }
        ],
    }


def write_architecture_rationale(state: AgentState) -> AgentState:
    work_dir = Path(state["work_dir"]).resolve()
    planning_dir = run_subdirs(work_dir)["planning"]
    planning_dir.mkdir(parents=True, exist_ok=True)
    path = planning_dir / f"round_{state['current_round']}_architecture_rationale.md"
    plan_json_path = planning_dir / f"round_{state['current_round']}_plan.json"
    lines = [
        f"# Round {state['current_round']} Architecture Rationale",
        "",
        f"Document description: {state.get('document_description') or '(not provided)'}",
        "",
        f"Optimization goal: {state['optimize_for']}",
        "",
    ]
    for arch in state["experiment_plan"]["architectures"]:
        lines.append(f"- {arch['architecture_name']}: {arch['reason']}")
        lines.append(
            f"  Params: pipeline_type={arch['pipeline_type']}, query_expansion={arch['query_expansion_method']}, top_k={arch['top_k']}, "
            f"final_top_k={arch['final_top_k']}, temperature={arch['temperature']}, "
            f"prompt_style={arch['prompt_style']}, primary_metric={arch['primary_metric']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        plan_json_path,
        {
            "round": state["current_round"],
            "round_goal": state["experiment_plan"].get("round_goal", ""),
            "primary_metric": metrics_for_goal(state["optimize_for"])["primary_metric"],
            "experiments": [
                {
                    "experiment_id": arch["architecture_name"],
                    "intent": arch["pipeline_type"],
                    "hypothesis": arch["reason"],
                    "config": {
                        "pipeline_type": arch["pipeline_type"],
                        "query_expansion_method": arch["query_expansion_method"],
                        "top_k": arch["top_k"],
                        "final_top_k": arch["final_top_k"],
                        "temperature": arch["temperature"],
                        "prompt_style": arch["prompt_style"],
                        "retrieval_metrics": arch["retrieval_metrics"],
                        "generator_metrics": arch["generator_metrics"],
                        "primary_metric": arch["primary_metric"],
                        "embedding_model": arch["embedding_model"],
                        "generator_model": arch["generator_model"],
                    },
                }
                for arch in state["experiment_plan"]["architectures"]
            ],
        },
    )
    return {
        **state,
        "architecture_rationale_paths": state.get("architecture_rationale_paths", []) + [str(path)],
    }


def write_configs(state: AgentState) -> AgentState:
    work_dir = Path(state["work_dir"]).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    plan = state["plan"]

    parse_config = {"modules": plan["parse_modules"]}
    chunk_config = {"modules": plan["chunk_modules"]}
    rag = plan["rag"]
    embedding_model = autorag_embedding_model(rag.get("embedding_model"))
    rag_config = {
        "vectordb": [
            {
                "name": "openai_chroma",
                "db_type": "chroma",
                "client_type": "persistent",
                "embedding_model": embedding_model,
                "collection_name": "agentic_openai",
                "path": str(work_dir / "optimization_project" / "resources" / "chroma"),
                "similarity_metric": "cosine",
                "embedding_batch": 16,
            }
        ],
        "node_lines": [
            {
                "node_line_name": "agentic_openai_rag",
                "nodes": [
                    {
                        "node_type": "semantic_retrieval",
                        "strategy": {
                            "metrics": ["retrieval_recall", "retrieval_precision", "retrieval_f1"],
                            "strategy": "mean",
                        },
                        "modules": [
                            {
                                "module_type": "vectordb",
                                "vectordb": "openai_chroma",
                                "top_k": rag["top_k"],
                                "embedding_batch": 8,
                            }
                        ],
                    },
                    {
                        "node_type": "prompt_maker",
                        "strategy": {"metrics": ["rouge"]},
                        "modules": [
                            {
                                "module_type": "fstring",
                                "prompt": (
                                    "Use only the retrieved passages to answer the question. "
                                    "If the answer is not present, say \"I don't know.\"\n\n"
                                    "Question:\n{query}\n\nRetrieved passages:\n{retrieved_contents}\n\nAnswer:\n"
                                ),
                            }
                        ],
                    },
                    {
                        "node_type": "generator",
                        "strategy": {"metrics": ["rouge"], "strategy": "mean"},
                        "modules": [
                            {
                                "module_type": "openai_llm",
                                "llm": normalize_autorag_generator_model(rag["generator_model"]),
                                "batch": 4,
                                "temperature": 0.0,
                            }
                        ],
                    },
                ],
            }
        ],
    }

    parse_path = work_dir / "parse_config.yaml"
    chunk_path = work_dir / "chunk_config.yaml"
    rag_path = work_dir / "rag_config.yaml"
    parse_path.write_text(yaml.safe_dump(parse_config, sort_keys=False), encoding="utf-8")
    chunk_path.write_text(yaml.safe_dump(chunk_config, sort_keys=False), encoding="utf-8")
    rag_path.write_text(yaml.safe_dump(rag_config, sort_keys=False), encoding="utf-8")

    return {
        **state,
        "parse_config_path": str(parse_path),
        "chunk_config_path": str(chunk_path),
        "rag_config_path": str(rag_path),
    }


def run_parse_and_chunk(state: AgentState) -> AgentState:
    work_dir = Path(state["work_dir"]).resolve()
    parse_dir = work_dir / "parse_project"
    chunk_dir = work_dir / "chunk_project"
    clean_dir(parse_dir)
    clean_dir(chunk_dir)

    parser = Parser(data_path_glob=str(Path(state["profile"]["input_dir"]).resolve() / "*"), project_dir=str(parse_dir))
    parser.start_parsing(state["parse_config_path"])
    parsed_path = parse_dir / "parsed_result.parquet"

    chunker = Chunker.from_parquet(str(parsed_path), project_dir=str(chunk_dir))
    chunker.start_chunking(state["chunk_config_path"])

    selected_corpus = chunk_dir / "0.parquet"
    corpus_out = work_dir / "corpus.parquet"
    raw_out = work_dir / "raw.parquet"
    pd.read_parquet(parsed_path, engine="pyarrow").to_parquet(raw_out, index=False)
    pd.read_parquet(selected_corpus, engine="pyarrow").to_parquet(corpus_out, index=False)
    return {**state, "raw_path": str(raw_out), "corpus_path": str(corpus_out)}


def create_qa(state: AgentState) -> AgentState:
    patch_openai_clients_for_local_ssl()
    work_dir = Path(state["work_dir"]).resolve()
    raw_df = pd.read_parquet(state["raw_path"], engine="pyarrow")
    corpus_df = pd.read_parquet(state["corpus_path"], engine="pyarrow")
    configured_sample_count = state.get("qa_sample_count") or os.environ.get("AUTORAG_AGENT_QA_SAMPLES", "24")
    sample_count = min(int(configured_sample_count), len(corpus_df))
    if sample_count <= 0:
        raise ValueError("No corpus rows available for QA generation")

    client = async_openai_client()
    corpus = Corpus(corpus_df, Raw(raw_df))
    qa = (
        corpus.sample(random_single_hop, n=sample_count, random_state=42)
        .map(lambda df: df.reset_index(drop=True))
        .make_retrieval_gt_contents()
        .batch_apply(factoid_query_gen, client=client, model_name=autorag_agent_model(), lang="en")
        .batch_apply(make_concise_gen_gt, client=client, model_name=autorag_agent_model(), lang="en")
        .filter(dontknow_filter_rule_based, lang="en")
    )
    qa_path = work_dir / "qa.parquet"
    qa.to_parquet(str(qa_path), state["corpus_path"])
    return {**state, "qa_path": str(qa_path)}


def run_optimization(state: AgentState) -> AgentState:
    patch_openai_clients_for_local_ssl()
    project_dir = Path(state["work_dir"]).resolve() / "optimization_project"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    evaluator = Evaluator(
        qa_data_path=state["qa_path"],
        corpus_data_path=state["corpus_path"],
        project_dir=str(project_dir),
    )
    evaluator.start_trial(state["rag_config_path"], skip_validation=True, full_ingest=True)
    return {**state, "optimization_project_dir": str(project_dir)}


def metric_value(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = []
    for row in rows:
        for key, value in row.items():
            if key == metric or key.endswith(f"_{metric}"):
                if value is not None:
                    values.append(value)
    if not values:
        return None
    return float(values[0])


def collect_node_summaries(project_dir: Path) -> dict[str, list[dict[str, Any]]]:
    node_dir = project_dir / "0" / "agentic_openai_rag"
    summaries: dict[str, list[dict[str, Any]]] = {}
    if not node_dir.exists():
        return summaries
    for summary_path in node_dir.glob("*/summary.csv"):
        summaries[summary_path.parent.name] = pd.read_csv(summary_path).to_dict(orient="records")
    return summaries


def flatten_metrics(node_summaries: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    metric_values: dict[str, float] = {}
    node_priority = [
        "query_expansion",
        "semantic_retrieval",
        "lexical_retrieval",
        "hybrid_retrieval",
        "prompt_maker",
        "generator",
    ]
    for node_name in node_priority:
        rows = node_summaries.get(node_name, [])
        if not rows:
            continue
        best_rows = [row for row in rows if bool(row.get("is_best"))] or [rows[0]]
        row = best_rows[0]
        for key, value in row.items():
            supported_metric_names = ["retrieval_recall", "retrieval_precision", "retrieval_f1", "rouge", "g_eval"]
            if key in set(supported_metric_names) or key.endswith(tuple(f"_{name}" for name in supported_metric_names)):
                canonical = key
                for supported_metric_name in supported_metric_names:
                    if key == supported_metric_name or key.endswith(f"_{supported_metric_name}"):
                        canonical = supported_metric_name
                if value is not None:
                    metric_values[canonical] = float(value)
    return metric_values


def run_experiment_round(state: AgentState) -> AgentState:
    patch_openai_clients_for_local_ssl()
    work_dir = Path(state["work_dir"]).resolve()
    round_dir = run_subdirs(work_dir)["experiments"] / f"round_{state['current_round']}"
    round_dir.mkdir(parents=True, exist_ok=True)
    round_results = []

    for arch in state["experiment_plan"]["architectures"]:
        arch_name = arch["architecture_name"]
        arch_dir = round_dir / arch_name
        project_dir = arch_dir / "optimization_project"
        if arch_dir.exists():
            shutil.rmtree(arch_dir)
        arch_dir.mkdir(parents=True, exist_ok=True)

        started_at = utc_now_iso()
        start_time = time.time()
        rag_config = build_rag_config(arch, project_dir)
        rag_path = arch_dir / "rag_config.yaml"
        rag_path.write_text(yaml.safe_dump(rag_config, sort_keys=False), encoding="utf-8")
        config_payload = {
            "experiment_id": arch_name,
            "round": state["current_round"],
            "intent": arch["pipeline_type"],
            "hypothesis": arch["reason"],
            "config_yaml_path": path_for_report(rag_path),
            "config": {
                "pipeline_type": arch["pipeline_type"],
                "query_expansion_method": arch["query_expansion_method"],
                "top_k": arch["top_k"],
                "final_top_k": arch["final_top_k"],
                "temperature": arch["temperature"],
                "prompt_style": arch["prompt_style"],
                "retrieval_metrics": arch["retrieval_metrics"],
                "generator_metrics": arch["generator_metrics"],
                "primary_metric": arch["primary_metric"],
                "embedding_model": arch["embedding_model"],
                "generator_model": arch["generator_model"],
            },
        }
        config_path = arch_dir / "config.json"
        write_json(config_path, config_payload)
        write_json(
            arch_dir / "status.json",
            {
                "status": "running",
                "phase": "optimization",
                "started_at": started_at,
                "progress_completed": 0,
                "progress_total": 1,
                "progress_percent": 0.0,
                "num_gpus": 0,
            },
        )

        evaluator = Evaluator(
            qa_data_path=state["qa_path"],
            corpus_data_path=state["corpus_path"],
            project_dir=str(project_dir),
        )
        evaluator.start_trial(str(rag_path), skip_validation=True, full_ingest=True)

        trial_summary = pd.read_csv(project_dir / "0" / "summary.csv").to_dict(orient="records")
        node_summaries = collect_node_summaries(project_dir)
        retrieval_summary = node_summaries.get("semantic_retrieval", [])
        generator_summary = node_summaries.get("generator", [])
        eval_metrics = flatten_metrics(node_summaries)
        primary = arch["primary_metric"]
        primary_score = eval_metrics.get(primary)
        elapsed_seconds = round(time.time() - start_time, 3)
        secondary_metrics = {key: value for key, value in eval_metrics.items() if key != primary}
        metrics_payload = {
            "evaluation": eval_metrics,
            "primary_metric": primary,
            "primary_metric_value": primary_score,
            "secondary_metrics": secondary_metrics,
            "rag_strategy": {
                "pipeline_type": arch["pipeline_type"],
                "query_expansion_method": arch["query_expansion_method"],
                "top_k": arch["top_k"],
                "final_top_k": arch["final_top_k"],
                "prompt_style": arch["prompt_style"],
            },
            "dataset": {
                "qa_path": path_for_report(state["qa_path"]),
                "corpus_path": path_for_report(state["corpus_path"]),
            },
            "timing": {
                "started_at": started_at,
                "elapsed_seconds": elapsed_seconds,
            },
            "num_gpus": 0,
        }
        metrics_path = arch_dir / "metrics.json"
        write_json(metrics_path, metrics_payload)
        publish_experiment_result(
            session_id=state["session_id"],
            designer="autorag",
            run_id=state["run_id"],
            round_number=state["current_round"],
            experiment_id=arch_name,
            config_path=config_path,
            metrics_path=metrics_path,
            config=config_payload,
            metrics=metrics_payload,
        )
        write_json(
            arch_dir / "status.json",
            {
                "status": "completed",
                "phase": "completed",
                "started_at": started_at,
                "elapsed_seconds": elapsed_seconds,
                "estimated_remaining_seconds": 0,
                "progress_completed": 1,
                "progress_total": 1,
                "progress_percent": 100.0,
                "num_gpus": 0,
            },
        )
        (arch_dir / "logs.txt").write_text(
            "\n".join(
                [
                    f"Started at: {started_at}",
                    f"Completed in: {elapsed_seconds}s",
                    f"AutoRAG project: {path_for_report(project_dir)}",
                    f"Primary metric: {primary}={primary_score}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        round_results.append(
            {
                "round": state["current_round"],
                "experiment_id": arch_name,
                "architecture_name": arch_name,
                "reason": arch["reason"],
                "pipeline_type": arch["pipeline_type"],
                "query_expansion_method": arch["query_expansion_method"],
                "top_k": arch["top_k"],
                "final_top_k": arch["final_top_k"],
                "filter_threshold": arch["filter_threshold"],
                "reranker_type": arch["reranker_type"],
                "primary_metric": primary,
                "primary_score": primary_score,
                "eval_metrics": eval_metrics,
                "rag_config_path": str(rag_path),
                "metrics_path": str(arch_dir / "metrics.json"),
                "status_path": str(arch_dir / "status.json"),
                "optimization_project_dir": str(project_dir),
                "trial_summary": trial_summary,
                "node_summaries": node_summaries,
                "retrieval_summary": retrieval_summary,
                "generator_summary": generator_summary,
            }
        )

    return {
        **state,
        "experiment_history": state.get("experiment_history", []) + round_results,
    }


def write_eval_results(state: AgentState) -> AgentState:
    work_dir = Path(state["work_dir"]).resolve()
    reports_dir = run_subdirs(work_dir)["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"round_{state['current_round']}_eval_results.md"
    json_path = reports_dir / f"round_{state['current_round']}_eval_results.json"
    current_results = [
        result
        for result in state["experiment_history"]
        if result["round"] == state["current_round"]
    ]
    lines = [
        f"# Round {state['current_round']} Evaluation Results",
        "",
        f"Document description: {state.get('document_description') or '(not provided)'}",
        "",
        f"Optimization goal: {state['optimize_for']}",
        "",
    ]
    for result in current_results:
        metrics = result.get("eval_metrics", {})
        lines.append(
            f"- {result['architecture_name']}: "
            f"{result['primary_metric']}={result['primary_score']}; "
            f"pipeline_type={result.get('pipeline_type')}; "
            f"query_expansion={result.get('query_expansion_method')}; "
            f"retrieval_recall={metrics.get('retrieval_recall')}; "
            f"retrieval_precision={metrics.get('retrieval_precision')}; "
            f"retrieval_f1={metrics.get('retrieval_f1')}; "
            f"rouge={metrics.get('rouge')}; "
            f"g_eval={metrics.get('g_eval')}"
        )
        lines.append(f"  Config: {result['rag_config_path']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        json_path,
        {
            "round": state["current_round"],
            "document_description": state.get("document_description") or "",
            "optimization_goal": state["optimize_for"],
            "results": [
                {
                    "experiment_id": result.get("experiment_id", result["architecture_name"]),
                    "status": "completed",
                    "primary_metric": result["primary_metric"],
                    "primary_metric_value": result["primary_score"],
                    "evaluation": result.get("eval_metrics", {}),
                    "config_yaml_path": path_for_report(result["rag_config_path"]),
                    "metrics_path": path_for_report(result.get("metrics_path", "")),
                    "optimization_project_dir": path_for_report(result["optimization_project_dir"]),
                }
                for result in current_results
            ],
        },
    )
    return {
        **state,
        "eval_results_paths": state.get("eval_results_paths", []) + [str(path)],
    }


def advance_round(state: AgentState) -> AgentState:
    return {**state, "current_round": state["current_round"] + 1}


def should_continue_experiments(state: AgentState) -> str:
    if state["current_round"] <= state["max_rounds"]:
        return "continue"
    return "done"


def experiment_manifest(state: AgentState, result: dict[str, Any], manifest_path: Path | None = None) -> dict[str, Any]:
    secondary_metrics = {
        key: value for key, value in result.get("eval_metrics", {}).items() if key != result.get("primary_metric")
    }
    payload = {
        "run_id": state.get("run_id", Path(state["work_dir"]).name),
        "round": result["round"],
        "experiment_id": result.get("experiment_id", result["architecture_name"]),
        "config_yaml_path": path_for_report(result["rag_config_path"]),
        "metrics_path": path_for_report(result.get("metrics_path", "")),
        "optimization_project_dir": path_for_report(result["optimization_project_dir"]),
        "primary_metric": result["primary_metric"],
        "primary_metric_value": result["primary_score"],
        "secondary_metrics": secondary_metrics,
        "rag_strategy": {
            "pipeline_type": result["pipeline_type"],
            "query_expansion_method": result["query_expansion_method"],
            "top_k": result["top_k"],
            "final_top_k": result["final_top_k"],
        },
    }
    if manifest_path is not None:
        payload["manifest_path"] = path_for_report(manifest_path)
    return payload


def write_leaderboard(path: Path, history: list[dict[str, Any]], round_winner_paths: dict[int, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "round",
        "experiment_id",
        "status",
        "primary_metric",
        "primary_metric_value",
        "secondary_metrics",
        "config_yaml_path",
        "metrics_path",
        "optimization_project_dir",
        "model_manifest_path",
        "error_summary",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in history:
            secondary_metrics = {
                key: value for key, value in result.get("eval_metrics", {}).items() if key != result.get("primary_metric")
            }
            writer.writerow(
                {
                    "round": result["round"],
                    "experiment_id": result.get("experiment_id", result["architecture_name"]),
                    "status": "completed",
                    "primary_metric": result["primary_metric"],
                    "primary_metric_value": result["primary_score"],
                    "secondary_metrics": secondary_metrics,
                    "config_yaml_path": path_for_report(result["rag_config_path"]),
                    "metrics_path": path_for_report(result.get("metrics_path", "")),
                    "optimization_project_dir": path_for_report(result["optimization_project_dir"]),
                    "model_manifest_path": round_winner_paths.get(result["round"], "")
                    if result.get("is_round_winner")
                    else "",
                    "error_summary": "",
                }
            )


def summarize_results(state: AgentState) -> AgentState:
    work_dir = Path(state["work_dir"]).resolve()
    reports_dir = run_subdirs(work_dir)["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    history = state.get("experiment_history", [])
    sorted_history = sorted(
        history,
        key=lambda item: (item.get("primary_score") is None, -(item.get("primary_score") or -1)),
    )
    best = sorted_history[0] if sorted_history else None

    round_winners: dict[int, dict[str, Any]] = {}
    for result in history:
        current = round_winners.get(result["round"])
        if current is None or (result.get("primary_score") or -1) > (current.get("primary_score") or -1):
            round_winners[result["round"]] = result
    round_winner_paths: dict[int, str] = {}
    for round_number, winner in sorted(round_winners.items()):
        for result in history:
            if result is winner:
                result["is_round_winner"] = True
        manifest_path = reports_dir / f"round_{round_number}_winner_model_manifest.json"
        write_json(manifest_path, experiment_manifest(state, winner, manifest_path))
        round_winner_paths[round_number] = path_for_report(manifest_path)

    final_manifest_path = reports_dir / "final_model_manifest.json"
    if best:
        write_json(final_manifest_path, experiment_manifest(state, best, final_manifest_path))

    leaderboard_path = reports_dir / "leaderboard.csv"
    write_leaderboard(leaderboard_path, history, round_winner_paths)

    final_recommendation_path = reports_dir / "final_recommendation.json"
    final_recommendation_md_path = reports_dir / "final_recommendation.md"
    if best:
        secondary_metrics = {
            key: value for key, value in best.get("eval_metrics", {}).items() if key != best.get("primary_metric")
        }
        final_recommendation = {
            "run_id": state.get("run_id", work_dir.name),
            "task_type": "rag_optimization",
            "best_experiment_id": best.get("experiment_id", best["architecture_name"]),
            "best_score": best["primary_score"],
            "primary_metric": best["primary_metric"],
            "secondary_metrics": secondary_metrics,
            "holdout_metrics_path": path_for_report(best.get("metrics_path", "")),
            "winning_model_path": path_for_report(best["optimization_project_dir"]),
            "winning_model_manifest_path": path_for_report(final_manifest_path),
            "winning_config_yaml_path": path_for_report(best["rag_config_path"]),
            "why_selected": "Highest primary metric across all completed experiments.",
            "optimization_loop_actions": [
                "Generated AutoRAG-compatible raw, corpus, and QA datasets.",
                "Recorded AutoRAG evaluation metrics for every completed experiment.",
                "Reviewed secondary retrieval and generation metric tradeoffs in the round summaries.",
                "Packaged round-winning and final-winning RAG manifests.",
            ],
        }
    else:
        final_recommendation = {
            "run_id": state.get("run_id", work_dir.name),
            "task_type": "rag_optimization",
            "best_experiment_id": None,
            "best_score": None,
            "why_selected": "No completed experiments were available.",
        }
    write_json(final_recommendation_path, final_recommendation)
    final_recommendation_md_path.write_text(
        "\n".join(
            [
                f"# Final Recommendation: {state.get('run_id', work_dir.name)}",
                "",
                f"Best experiment: `{final_recommendation.get('best_experiment_id')}`",
                f"Primary metric: `{final_recommendation.get('primary_metric')}`",
                f"Best score: `{final_recommendation.get('best_score')}`",
                f"Config YAML: `{final_recommendation.get('winning_config_yaml_path')}`",
                f"Model manifest: `{final_recommendation.get('winning_model_manifest_path')}`",
                f"Metrics: `{final_recommendation.get('holdout_metrics_path')}`",
                "",
                final_recommendation.get("why_selected", ""),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    research_lines = [f"# Research Log: {state.get('run_id', work_dir.name)}", ""]
    for round_number in sorted({result["round"] for result in history}):
        round_results = [result for result in history if result["round"] == round_number]
        winner = round_winners.get(round_number)
        plan_goal = ""
        for path in state.get("architecture_rationale_paths", []):
            if f"round_{round_number}_" in Path(path).name:
                plan_goal = Path(path).read_text(encoding="utf-8").splitlines()[0]
        research_lines.extend(
            [
                f"## Round {round_number}",
                "",
                state.get("experiment_plan", {}).get("round_goal", "") if round_number == state.get("current_round") else plan_goal,
                "",
                "Optimization loop checks completed:",
                "",
                "- AutoRAG metrics were recorded for every completed experiment.",
                "- Secondary retrieval and generation tradeoffs were reviewed.",
                "- The round winner was packaged through a manifest.",
                "",
            ]
        )
        if winner:
            research_lines.append(
                f"Winner: `{winner.get('experiment_id', winner['architecture_name'])}` with {winner['primary_metric']}={winner['primary_score']}."
            )
            research_lines.append("")
        research_lines.extend(
            [
                "| Experiment | Status | Primary Metric | Value | Secondary Metrics | Hypothesis Result |",
                "|---|---|---|---:|---|---|",
            ]
        )
        for result in round_results:
            secondary_metrics = {
                key: value for key, value in result.get("eval_metrics", {}).items() if key != result.get("primary_metric")
            }
            research_lines.append(
                f"| {result.get('experiment_id', result['architecture_name'])} | completed | "
                f"{result['primary_metric']} | {result['primary_score']} | {secondary_metrics} | "
                f"{'supported' if result is winner else 'inconclusive'} |"
            )
        research_lines.append("")
    (reports_dir / "research_log.md").write_text("\n".join(research_lines) + "\n", encoding="utf-8")

    report = {
        "run_id": state.get("run_id", work_dir.name),
        "profile": state["profile"],
        "parse_chunk_plan": state["plan"],
        "document_description": state.get("document_description", ""),
        "optimize_for": state["optimize_for"],
        "parse_config": path_for_report(state["parse_config_path"]),
        "chunk_config": path_for_report(state["chunk_config_path"]),
        "raw_path": path_for_report(state["raw_path"]),
        "corpus_path": path_for_report(state["corpus_path"]),
        "qa_path": path_for_report(state["qa_path"]),
        "architecture_rationale_paths": state.get("architecture_rationale_paths", []),
        "eval_results_paths": state.get("eval_results_paths", []),
        "best_experiment": best,
        "experiment_history": history,
        "reports": {
            "leaderboard": path_for_report(leaderboard_path),
            "final_recommendation": path_for_report(final_recommendation_path),
            "final_model_manifest": path_for_report(final_manifest_path),
            "research_log": path_for_report(reports_dir / "research_log.md"),
        },
    }
    report_path = reports_dir / "agent_report.json"
    write_json(report_path, report)
    write_json(
        work_dir / "status.json",
        {
            "run_id": state.get("run_id", work_dir.name),
            "status": "completed",
            "final_recommendation_path": path_for_report(final_recommendation_path),
        },
    )
    return {**state, "report_path": str(report_path)}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("inspect_documents", inspect_documents)
    graph.add_node("plan_configs", plan_configs)
    graph.add_node("write_configs", write_configs)
    graph.add_node("run_parse_and_chunk", run_parse_and_chunk)
    graph.add_node("create_qa", create_qa)
    graph.add_node("plan_experiment_round", plan_experiment_round)
    graph.add_node("write_architecture_rationale", write_architecture_rationale)
    graph.add_node("run_experiment_round", run_experiment_round)
    graph.add_node("write_eval_results", write_eval_results)
    graph.add_node("advance_round", advance_round)
    graph.add_node("summarize_results", summarize_results)

    graph.set_entry_point("inspect_documents")
    graph.add_edge("inspect_documents", "plan_configs")
    graph.add_edge("plan_configs", "write_configs")
    graph.add_edge("write_configs", "run_parse_and_chunk")
    graph.add_edge("run_parse_and_chunk", "create_qa")
    graph.add_edge("create_qa", "plan_experiment_round")
    graph.add_edge("plan_experiment_round", "write_architecture_rationale")
    graph.add_edge("write_architecture_rationale", "run_experiment_round")
    graph.add_edge("run_experiment_round", "write_eval_results")
    graph.add_edge("write_eval_results", "advance_round")
    graph.add_conditional_edges(
        "advance_round",
        should_continue_experiments,
        {
            "continue": "plan_experiment_round",
            "done": "summarize_results",
        },
    )
    graph.add_edge("summarize_results", END)
    return graph.compile()


def main() -> int:
    root = Path.cwd()
    load_dotenv(root / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", default=".")
    parser.add_argument(
        "--work-dir",
        default="runs",
        help='Output root. If this path starts with "run_", it is used as the run folder; otherwise a new run_<timestamp>_<id> folder is created inside it.',
    )
    parser.add_argument(
        "--document-description",
        default="",
        help='Human description of the document content, for example: "PDFs with images and tables".',
    )
    parser.add_argument(
        "--optimize-for",
        default="balanced retrieval and answer quality",
        help='Human goal for optimization, for example: "reduce hallucinations" or "do not miss key details".',
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument("--architectures-per-round", type=int, default=DEFAULT_ARCHITECTURES_PER_ROUND)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--emit-artifact", action="store_true", default=False, help="Generate a deployable artifact zip after the run completes (default: False).")
    parser.add_argument("--no-emit-artifact", dest="emit_artifact", action="store_false", help="Skip artifact generation.")
    args = parser.parse_args()

    require_openai_api_key(context="AutoRAG designer CLI")
    configure_openai_environment()

    run_id, work_dir = resolve_run_dir(args.work_dir, args.fresh)
    write_json(
        work_dir / "status.json",
        {
            "run_id": run_id,
            "status": "running",
            "started_at": utc_now_iso(),
        },
    )

    app = build_graph()
    final_state = app.invoke(
        {
            "run_id": run_id,
            "docs_dir": str(Path(args.docs_dir).resolve()),
            "work_dir": str(work_dir),
            "document_description": args.document_description,
            "optimize_for": args.optimize_for,
            "max_rounds": args.rounds,
            "architectures_per_round": args.architectures_per_round,
            "qa_sample_count": int(os.environ.get("AUTORAG_AGENT_QA_SAMPLES", "24")),
            "current_round": 1,
            "experiment_history": [],
            "architecture_rationale_paths": [],
            "eval_results_paths": [],
        }
    )
    print(f"Agentic AutoRAG run complete: {work_dir}")
    print(f"Report: {final_state['report_path']}")
    print(f"Architecture rationale files: {final_state['architecture_rationale_paths']}")
    print(f"Evaluation result files: {final_state['eval_results_paths']}")

    if args.emit_artifact:
        try:
            from vectorforge_v1.artifact_forge import generate_artifact
            rec_path = work_dir / "reports" / "final_recommendation.json"
            if rec_path.exists():
                import json as _json
                rec = _json.loads(rec_path.read_text(encoding="utf-8"))
                winner = {
                    "best_experiment_id": rec.get("best_experiment_id"),
                    "primary_metric": rec.get("primary_metric"),
                    "best_score": rec.get("best_score"),
                    "secondary_metrics": rec.get("secondary_metrics", {}),
                    "winning_config_yaml_path": rec.get("winning_config_yaml_path"),
                    "corpus_path": str(work_dir / "corpus.parquet"),
                }
                zip_path = generate_artifact(
                    "autorag",
                    run_id=run_id,
                    winner=winner,
                    run_dir=work_dir,
                )
                if zip_path:
                    print(f"Artifact: {zip_path}")
        except Exception as exc:
            print(f"Artifact generation failed (non-fatal): {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
