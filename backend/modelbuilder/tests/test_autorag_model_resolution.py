from vectorforge_v1.exp_designer.gen_ai.autorag.agentic_autorag import (
    DEFAULT_RAG_MODEL,
    autorag_embedding_model,
    autorag_agent_model,
    normalize_openai_chat_model,
)


def test_autorag_agent_model_uses_openai_model_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-4o-mini")
    monkeypatch.delenv("AUTORAG_AGENT_MODEL", raising=False)
    monkeypatch.delenv("VECTORFORGE_AUTORAG_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("AUTORAG_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("VECTORFORGE_OPENAI_MODEL", raising=False)

    assert autorag_agent_model() == "gpt-4o-mini"


def test_normalize_openai_chat_model_handles_provider_prefixes():
    assert normalize_openai_chat_model("openai/gpt-4o-mini") == "gpt-4o-mini"
    assert normalize_openai_chat_model("anthropic/claude-sonnet-4.6") == DEFAULT_RAG_MODEL


def test_autorag_embedding_model_uses_openai_embedding_env(monkeypatch):
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.delenv("AUTORAG_AGENT_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("VECTORFORGE_AUTORAG_OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("AUTORAG_OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("VECTORFORGE_AUTORAG_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("AUTORAG_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("VECTORFORGE_OPENAI_EMBEDDING_MODEL", raising=False)

    assert autorag_embedding_model() == "openai_embed_3_large"
