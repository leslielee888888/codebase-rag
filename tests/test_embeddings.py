"""Unit tests for embeddings.py. OllamaEmbeddingClient's network call is
mocked — these never require a running Ollama server."""

from types import SimpleNamespace

from codebase_rag.embeddings import OllamaEmbeddingClient


def test_embed_empty_list_short_circuits_without_calling_ollama():
    client = OllamaEmbeddingClient()
    assert client.embed([]) == []


def test_embed_returns_one_vector_per_text(monkeypatch):
    client = OllamaEmbeddingClient()
    fake_response = SimpleNamespace(embeddings=[[0.1, 0.2], [0.3, 0.4]])
    monkeypatch.setattr(client._client, "embed", lambda model, input: fake_response)

    result = client.embed(["first chunk", "second chunk"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_host_resolves_from_ollama_host_env_var(monkeypatch):
    """docker-compose.yml sets OLLAMA_HOST=http://ollama:11434 for the app
    container — localhost there would mean the app container itself, not the
    sibling ollama service, so this must actually be read."""
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")

    client = OllamaEmbeddingClient()

    assert client._client._client.base_url == "http://ollama:11434"


def test_host_falls_back_to_default_without_the_env_var(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    client = OllamaEmbeddingClient()

    assert client._client._client.base_url == "http://localhost:11434"


def test_explicit_host_argument_overrides_the_env_var(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")

    client = OllamaEmbeddingClient(host="http://explicit-host:9999")

    assert client._client._client.base_url == "http://explicit-host:9999"
