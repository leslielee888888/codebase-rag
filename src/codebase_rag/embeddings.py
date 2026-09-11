"""Embedding client: `Qwen3-Embedding-0.6B` served locally via Ollama (§10 Q5).

Kept behind a small `EmbeddingClient` protocol so the indexing/query
pipelines never depend on Ollama's network API directly — real tests run
against a fake client; only a real Ollama server exercises `OllamaEmbeddingClient`.
"""

from __future__ import annotations

from typing import Protocol

DEFAULT_MODEL = "qwen3-embedding:0.6b"
DEFAULT_HOST = "http://localhost:11434"


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""
        ...


class OllamaEmbeddingClient:
    """Embeds via a local Ollama server (default: the NAS's `ollama` container)."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST):
        import ollama  # imported lazily so the CLI can start without it configured

        self._model = model
        self._client = ollama.Client(host=host)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embed(model=self._model, input=texts)
        return [list(vec) for vec in response.embeddings]
