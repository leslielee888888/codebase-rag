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
