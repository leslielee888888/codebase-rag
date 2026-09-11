"""Generation: Claude Sonnet 5 answers a question grounded in retrieved chunks (FR-2).

Sonnet 5 over Opus 5 (§10 Q5) — grounded Q&A over retrieved source isn't
frontier-reasoning work, and this runs per query. Auth is the SDK's default
profile chain (subscription OAuth via `ant auth login`), never a hardcoded
API key, per the standing preference — `anthropic.Anthropic()` with no args
resolves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You answer questions about a codebase using only the numbered source "
    "excerpts you're given. Ground every claim in a specific excerpt by "
    "referring to its number, like [2]. If the excerpts don't contain the "
    "answer, say so plainly instead of guessing."
)


@dataclass(frozen=True)
class RetrievedChunk:
    """One search result: `store.search()`'s row, named for readability."""

    similarity: float
    repo: str
    file_path: str
    start_line: int
    end_line: int
    content: str

    @property
    def citation(self) -> str:
        return f"{self.repo}/{self.file_path}:{self.start_line}-{self.end_line}"


class Generator(Protocol):
    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str:
        """Return an answer grounded in `chunks`."""
        ...


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    sources = "\n\n".join(
        f"[{i}] {c.citation}\n{c.content}" for i, c in enumerate(chunks, start=1)
    )
    return f"Sources:\n\n{sources}\n\nQuestion: {question}"


class ClaudeGenerator:
    """Generates via the Claude API (Sonnet 5, subscription OAuth auth)."""

    def __init__(self, model: str = MODEL):
        import anthropic  # imported lazily, mirrors OllamaEmbeddingClient

        self._model = model
        self._client = anthropic.Anthropic()

    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(question, chunks)}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
