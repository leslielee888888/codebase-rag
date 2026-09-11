"""Shared retrieve-then-generate pipeline (FR-1, FR-2, FR-6 of the v1 PRD;
T1 of the v2 dashboard PRD).

`cli.py`'s `_answer()` and the dashboard's `api.py` both need the same
pipeline: embed the question, search the store, generate a grounded answer,
log the query. Splitting it out here means it's implemented — and tested —
once, and reused as-is (§10 Q1 of the dashboard PRD: "wraps v1's already-
built, already-tested logic ... rather than reimplementing it").

This module does no I/O of its own beyond the pipeline itself — no printing,
no `sys.exit`. Every expected failure raises a typed `AnsweringError`
subclass with a plain-English message; each caller decides how to surface it
on its own surface (Typer echo + exit code for the CLI, an HTTP status +
JSON body for the API).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from codebase_rag.embeddings import EmbeddingClient
from codebase_rag.generation import Generator, RetrievedChunk, Turn
from codebase_rag.store import DEFAULT_DB_PATH, Store

TOP_K = 8
# Caps how many prior turns go into the generation prompt (FR-6). Without
# this, the prompt resends the whole conversation every turn — prompt size
# grows O(n) per turn and cumulative tokens sent over an n-turn session grow
# O(n^2). Retrieval already only ever looks at the single most recent turn,
# so this only bounds the generation side.
MAX_CHAT_HISTORY_TURNS = 6


class AnsweringError(Exception):
    """Base for every clean, expected failure in `answer_question`/`resolve_scope`."""


class NothingIndexedError(AnsweringError):
    """Nothing to search yet — no repos configured, or none indexed."""


class UnindexedRepoError(AnsweringError):
    """One or more repos in the requested scope haven't been indexed."""

    def __init__(self, repos: list[str]):
        self.repos = repos
        super().__init__(f"Not indexed yet: {repos}. Run 'codebase-rag index <repo>' for each first.")


class EmbeddingFailedError(AnsweringError):
    """Ollama unreachable, model not pulled, etc."""


class NoMatchError(AnsweringError):
    """The scoped search returned no rows to answer from."""


class GenerationFailedError(AnsweringError):
    """The generator (Claude) failed or timed out."""


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    chunks: list[RetrievedChunk]
    latency_ms: int


def resolve_scope(repos: list[str] | None, config_repo_names: list[str]) -> list[str]:
    """A query's repo scope: `repos` if given, else every configured repo.
    Raises `NothingIndexedError` if that still comes up empty (no `--repo`
    and no repos in config.yaml at all)."""
    scope = repos or config_repo_names
    if not scope:
        raise NothingIndexedError("No repos configured yet - run 'codebase-rag index <repo>' first.")
    return scope


def answer_question(
    question: str,
    scope: list[str],
    history: list[Turn] | None,
    embed_client: EmbeddingClient,
    generator: Generator,
    db_path: Path = DEFAULT_DB_PATH,
) -> AnswerResult:
    """Embed `question` (folding in the prior turn if there is one, FR-6),
    search `scope`, generate a grounded answer, and log the query. Callers
    supply their own `embed_client`/`generator` — this stays a pure pipeline,
    not a place that decides which concrete client to construct."""
    if not db_path.exists():
        raise NothingIndexedError("Nothing indexed yet - run 'codebase-rag index <repo>' first.")

    started_at = time.monotonic()
    # A follow-up's retrieval considers the prior turn too (FR-6) — "what
    # about the edge cases?" alone wouldn't retrieve anything useful.
    embed_text = question
    if history:
        last_question, last_answer = history[-1]
        embed_text = f"{last_question}\n{last_answer}\n{question}"
    try:
        [query_vector] = embed_client.embed([embed_text])
    except Exception as exc:
        raise EmbeddingFailedError(str(exc)) from exc

    with Store(db_path) as store:
        known = set(store.indexed_repos())
        unindexed = [r for r in scope if r not in known]
        if unindexed:
            raise UnindexedRepoError(unindexed)
        rows = store.search(query_vector, repos=scope, top_k=TOP_K)

    if not rows:
        raise NoMatchError("No indexed content matched - nothing to answer from.")

    chunks = [
        RetrievedChunk(similarity=sim, repo=repo, file_path=path, start_line=start, end_line=end, content=content)
        for sim, repo, path, start, end, content in rows
    ]

    capped_history = history[-MAX_CHAT_HISTORY_TURNS:] if history else history
    try:
        answer = generator.generate(question, chunks, capped_history)
    except Exception as exc:
        raise GenerationFailedError(str(exc)) from exc

    latency_ms = round((time.monotonic() - started_at) * 1000)
    with Store(db_path) as store:
        store.log_query(question, scope, num_results=len(chunks), latency_ms=latency_ms)

    return AnswerResult(answer=answer, chunks=chunks, latency_ms=latency_ms)
