"""LLM service via Vercel AI Gateway (OpenAI-compatible).

Uses the OpenAI SDK pointed at ai-gateway.vercel.sh/v1.
Structured output is achieved via tool/function calling.

Env vars:
    AI_GATEWAY_API_KEY  — Vercel AI Gateway key
    AI_GATEWAY_MODEL    — model string, e.g. "anthropic/claude-sonnet-4-6"
                          or "openai/gpt-4o". Defaults to anthropic/claude-sonnet-4-6.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from conversational.config import get_settings

_client: AsyncOpenAI | None = None

_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        api_key = settings.ai_gateway_api_key
        if not api_key:
            raise RuntimeError(
                "AI_GATEWAY_API_KEY is not set. "
                "Add it to conversational/.env and restart the server."
            )
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url=_GATEWAY_BASE_URL,
            http_client=httpx.AsyncClient(verify=settings.llm_ssl_verify),
        )
    return _client


def _active_model() -> str:
    settings = get_settings()
    return settings.ai_gateway_model or settings.llm_model or _DEFAULT_MODEL


async def structured_llm_call(
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    output_schema: dict[str, Any],
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call the gateway with forced function calling for structured JSON output.

    Args:
        system_prompt: System instructions.
        user_message: Content to process.
        tool_name: Function name the model must call.
        tool_description: What the function does.
        output_schema: JSON Schema for the function parameters.
        model: Override model string (e.g. "openai/gpt-4o").
        max_tokens: Maximum completion tokens.

    Returns:
        dict extracted from the function_call arguments.

    Raises:
        ValueError: If the model does not return a function call.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model=model or _active_model(),
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
    )

    choice = response.choices[0]
    tool_calls = choice.message.tool_calls or []
    for tc in tool_calls:
        if tc.type == "function" and tc.function.name == tool_name:
            return json.loads(tc.function.arguments)

    raise ValueError(
        f"Model did not return function call for '{tool_name}'. "
        f"Finish reason: {choice.finish_reason}."
    )


async def chat_llm_call(
    system_prompt: str,
    messages: list[ChatCompletionMessageParam],
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Plain conversational completion returning raw text."""
    client = _get_client()
    all_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        *messages,
    ]
    response = await client.chat.completions.create(
        model=model or _active_model(),
        max_tokens=max_tokens,
        messages=all_messages,
    )
    return response.choices[0].message.content or ""
