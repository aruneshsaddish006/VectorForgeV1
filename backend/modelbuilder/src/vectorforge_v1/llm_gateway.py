from __future__ import annotations

import json
import os
from typing import Any

import httpx
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel


CLAUDE_SONNET_4_6_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_AUTORAG_EMBEDDING_MODEL = "openai/text-embedding-3-small"
DEFAULT_AI_GATEWAY_MODEL = CLAUDE_SONNET_4_6_MODEL
DEFAULT_AUTOGLUON_AI_GATEWAY_MODEL = CLAUDE_SONNET_4_6_MODEL
DEFAULT_NARRATIVE_AI_GATEWAY_MODEL = CLAUDE_SONNET_4_6_MODEL
AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"

# Embeddings go direct to OpenAI (api.openai.com) with a real OPENAI_API_KEY,
# not through the AI Gateway.
OPENAI_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


def gateway_api_key(explicit: str | None = None) -> str | None:
    return (
        explicit
        or os.environ.get("VECTORFORGE_AI_GATEWAY_API_KEY")
        or os.environ.get("AI_GATEWAY_API_KEY")
        or os.environ.get("VERCEL_OIDC_TOKEN")
    )


def gateway_base_url(explicit: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("VECTORFORGE_AI_GATEWAY_BASE_URL")
        or os.environ.get("AI_GATEWAY_BASE_URL")
        or AI_GATEWAY_BASE_URL
    )


def openai_api_key(explicit: str | None = None) -> str | None:
    return (
        explicit
        or os.environ.get("VECTORFORGE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_KEY")
    )


def require_openai_api_key(explicit: str | None = None, context: str = "OpenAI embedding call") -> str:
    api_key = openai_api_key(explicit)
    if not api_key:
        raise RuntimeError(
            f"{context} requires an OpenAI API key. "
            "Set VECTORFORGE_OPENAI_API_KEY, OPENAI_API_KEY, or OPENAI_KEY."
        )
    return api_key


def gateway_model(explicit: str | None = None, fallback: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("VECTORFORGE_AI_GATEWAY_MODEL")
        or os.environ.get("AI_GATEWAY_MODEL")
        or fallback
        or DEFAULT_AI_GATEWAY_MODEL
    )


def openai_model(explicit: str | None = None, fallback: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("VECTORFORGE_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or fallback
        or "gpt-4o-mini"
    )


def gateway_embedding_model(explicit: str | None = None, fallback: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("VECTORFORGE_AUTORAG_EMBEDDING_MODEL")
        or os.environ.get("AUTORAG_EMBEDDING_MODEL")
        or os.environ.get("VECTORFORGE_AI_GATEWAY_EMBEDDING_MODEL")
        or os.environ.get("AI_GATEWAY_EMBEDDING_MODEL")
        or fallback
        or DEFAULT_AUTORAG_EMBEDDING_MODEL
    )


def openai_embedding_model(explicit: str | None = None, fallback: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("VECTORFORGE_AUTORAG_OPENAI_EMBEDDING_MODEL")
        or os.environ.get("AUTORAG_OPENAI_EMBEDDING_MODEL")
        or os.environ.get("VECTORFORGE_OPENAI_EMBEDDING_MODEL")
        or os.environ.get("OPENAI_EMBEDDING_MODEL")
        or fallback
        or DEFAULT_OPENAI_EMBEDDING_MODEL
    )


def normalize_gateway_embedding_model(model: str | None = None) -> str:
    resolved = gateway_embedding_model(model)
    alias_map = {
        "openai_embed_3_small": DEFAULT_AUTORAG_EMBEDDING_MODEL,
        "text-embedding-3-small": DEFAULT_AUTORAG_EMBEDDING_MODEL,
        "text-embedding-3-large": "openai/text-embedding-3-large",
        "text-embedding-ada-002": "openai/text-embedding-ada-002",
    }
    if resolved in alias_map:
        return alias_map[resolved]
    if resolved.startswith("text-embedding-"):
        return f"openai/{resolved}"
    return resolved


def normalize_openai_embedding_model(model: str | None = None) -> str:
    """Resolve an embedding model id to a *bare* OpenAI name for direct api.openai.com use.

    Strips any provider-style ``openai/`` prefix and maps aliases, so the model
    id is valid against OpenAI's API (which does not accept provider prefixes).
    """
    resolved = openai_embedding_model(model)
    alias_map = {
        "openai_embed_3_small": DEFAULT_OPENAI_EMBEDDING_MODEL,
        "openai_embed_3_large": "text-embedding-3-large",
        "openai": "text-embedding-ada-002",
    }
    if resolved in alias_map:
        return alias_map[resolved]
    if resolved.startswith("openai/"):
        return resolved.split("/", 1)[1]
    return resolved


def autorag_embedding_registry_key(model: str | None = None) -> str:
    """Resolve an embedding model id to an AutoRAG registry *key*.

    AutoRAG's config validates embedding_model against its named registry
    (openai_embed_3_small, openai_embed_3_large, openai), NOT raw OpenAI model
    strings. This maps a bare/prefixed OpenAI model name to the matching key.
    """
    bare = normalize_openai_embedding_model(model)
    key_map = {
        "text-embedding-3-small": "openai_embed_3_small",
        "text-embedding-3-large": "openai_embed_3_large",
        "text-embedding-ada-002": "openai",
    }
    return key_map.get(bare, bare)


def require_gateway_api_key(explicit: str | None = None, context: str = "LLM call") -> str:
    api_key = gateway_api_key(explicit)
    if not api_key:
        raise RuntimeError(
            f"{context} requires AI Gateway credentials. "
            "Set VECTORFORGE_AI_GATEWAY_API_KEY, AI_GATEWAY_API_KEY, or VERCEL_OIDC_TOKEN."
        )
    return api_key


def configure_ai_gateway_environment() -> None:
    api_key = require_gateway_api_key(context="AI Gateway environment")
    base_url = gateway_base_url()
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_BASE"] = base_url


def openai_client(api_key: str | None = None, *, ssl_verify: bool = False) -> OpenAI:
    return OpenAI(
        api_key=require_gateway_api_key(api_key, "AI Gateway client"),
        base_url=gateway_base_url(),
        http_client=httpx.Client(verify=ssl_verify),
    )


def async_openai_client(api_key: str | None = None, *, ssl_verify: bool = False) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=require_gateway_api_key(api_key, "AI Gateway async client"),
        base_url=gateway_base_url(),
        http_client=httpx.AsyncClient(verify=ssl_verify),
    )


def openai_embedding_client(api_key: str | None = None, *, ssl_verify: bool = False) -> OpenAI:
    """OpenAI client pointed directly at api.openai.com with a real OPENAI_API_KEY."""
    return OpenAI(
        api_key=require_openai_api_key(api_key, "OpenAI embedding client"),
        base_url=OPENAI_API_BASE_URL,
        http_client=httpx.Client(verify=ssl_verify),
    )


def openai_direct_client(api_key: str | None = None, *, ssl_verify: bool = False) -> OpenAI:
    """Sync OpenAI client pointed directly at api.openai.com with a real OPENAI_API_KEY."""
    return OpenAI(
        api_key=require_openai_api_key(api_key, "OpenAI direct client"),
        base_url=OPENAI_API_BASE_URL,
        http_client=httpx.Client(verify=ssl_verify),
    )


def async_openai_direct_client(api_key: str | None = None, *, ssl_verify: bool = False) -> AsyncOpenAI:
    """Async OpenAI client pointed directly at api.openai.com with a real OPENAI_API_KEY."""
    return AsyncOpenAI(
        api_key=require_openai_api_key(api_key, "OpenAI async direct client"),
        base_url=OPENAI_API_BASE_URL,
        http_client=httpx.AsyncClient(verify=ssl_verify),
    )


def model_json_schema(model_type: type[BaseModel]) -> dict[str, Any]:
    return model_type.model_json_schema()


def structured_llm_call(
    *,
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    output_schema: dict[str, Any],
    api_key: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    max_tokens: int = 4096,
    ssl_verify: bool = False,
) -> dict[str, Any]:
    client = openai_client(api_key, ssl_verify=ssl_verify)
    response = client.chat.completions.create(
        model=gateway_model(model, fallback_model),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": output_schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
        stream=False,
    )

    choice = response.choices[0]
    for tool_call in choice.message.tool_calls or []:
        if tool_call.type == "function" and tool_call.function.name == tool_name:
            return json.loads(tool_call.function.arguments)

    raise ValueError(
        f"Model did not return function call for '{tool_name}'. "
        f"Finish reason: {choice.finish_reason}."
    )


def structured_openai_llm_call(
    *,
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    output_schema: dict[str, Any],
    api_key: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    max_tokens: int = 4096,
    ssl_verify: bool = False,
) -> dict[str, Any]:
    client = openai_direct_client(api_key, ssl_verify=ssl_verify)
    response = client.chat.completions.create(
        model=openai_model(model, fallback_model),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": output_schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
        stream=False,
    )

    choice = response.choices[0]
    for tool_call in choice.message.tool_calls or []:
        if tool_call.type == "function" and tool_call.function.name == tool_name:
            return json.loads(tool_call.function.arguments)

    raise ValueError(
        f"Model did not return function call for '{tool_name}'. "
        f"Finish reason: {choice.finish_reason}."
    )


def chat_llm_call(
    *,
    system_prompt: str,
    messages: list[ChatCompletionMessageParam],
    api_key: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    max_tokens: int = 1024,
    ssl_verify: bool = False,
) -> str:
    client = openai_client(api_key, ssl_verify=ssl_verify)
    response = client.chat.completions.create(
        model=gateway_model(model, fallback_model),
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        stream=False,
    )
    return response.choices[0].message.content or ""


def embedding_call(
    *,
    input: str | list[str],
    api_key: str | None = None,
    model: str | None = None,
    ssl_verify: bool = False,
) -> list[list[float]]:
    # Embeddings go direct to OpenAI with a real OPENAI_API_KEY (not the AI Gateway).
    client = openai_embedding_client(api_key, ssl_verify=ssl_verify)
    response = client.embeddings.create(
        model=normalize_openai_embedding_model(model),
        input=input,
    )
    return [item.embedding for item in response.data]
