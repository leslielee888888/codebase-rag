"""Dashboard API (T1 of the v2 PRD): a FastAPI service wrapping v1's
already-built, already-tested pipeline directly (`answering.answer_question`,
`config.load_config`) rather than reimplementing it (§10 Q1).

This is the first slice — `POST /query` (FR-1, FR-2, FR-6) plus a bare
`GET /health`. The repos/reindex/stats endpoints land in T3-T6; the frontend
that calls this in T7-T10; deploying it alongside `app`/`ollama` in T11.

Run locally with `uvicorn codebase_rag.api:app --reload`, or via the
`codebase-rag-api` console script (`python -m codebase_rag.api`).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from codebase_rag import answering
from codebase_rag.config import ConfigError, load_config
from codebase_rag.embeddings import EmbeddingClient, OllamaEmbeddingClient
from codebase_rag.generation import ClaudeGenerator, Generator, Turn
from codebase_rag.store import DEFAULT_DB_PATH, Store

app = FastAPI(title="codebase-rag dashboard API", version="0.1.0")

# Maps each AnsweringError subclass to the HTTP status that best fits it —
# a caller's fault worth surfacing distinctly (400/404/409) vs. an upstream
# dependency failing (502). Order matters: more specific subclasses first,
# since UnindexedRepoError/NoMatchError/NothingIndexedError all descend from
# AnsweringError and dict lookup by exact type only matches the first hit
# found via isinstance below.
_STATUS_FOR_ERROR: list[tuple[type[answering.AnsweringError], int]] = [
    (answering.NothingIndexedError, 409),
    (answering.UnindexedRepoError, 409),
    (answering.NoMatchError, 404),
    (answering.EmbeddingFailedError, 502),
    (answering.GenerationFailedError, 502),
]


def _status_for(exc: answering.AnsweringError) -> int:
    for error_type, status in _STATUS_FOR_ERROR:
        if isinstance(exc, error_type):
            return status
    return 500  # pragma: no cover - every current subclass is listed above


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    repos: list[str] | None = Field(default=None, description="Scope (FR-2). Omit for every configured repo.")
    history: list[Turn] | None = Field(default=None, description="Prior (question, answer) turns (FR-6).")


class CitationOut(BaseModel):
    """Citation metadata only — the exact snippet behind one (FR-3) is a
    separate lookup, not part of this response (T2)."""

    index: int
    repo: str
    file_path: str
    start_line: int
    end_line: int
    citation: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    latency_ms: int


class CitationContentResponse(BaseModel):
    content: str


class RepoOut(BaseModel):
    name: str
    path: str
    indexed: bool
    last_indexed_at: str | None = None


class ReposResponse(BaseModel):
    repos: list[RepoOut]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/repos", response_model=ReposResponse)
def repos() -> ReposResponse:
    """Every configured repo, with whether it's indexed and (if so) when it
    was last indexed (FR-4, T3)."""
    try:
        config = load_config()
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status: dict[str, str] = {}
    if DEFAULT_DB_PATH.exists():
        with Store(DEFAULT_DB_PATH) as store:
            status = store.repo_status()

    return ReposResponse(
        repos=[
            RepoOut(name=r.name, path=r.path, indexed=r.name in status, last_indexed_at=status.get(r.name))
            for r in config.repos
        ]
    )


@app.get("/citation", response_model=CitationContentResponse)
def citation(repo: str, file_path: str, start_line: int, end_line: int) -> CitationContentResponse:
    """The exact snippet behind a citation the /query endpoint already
    returned (FR-3, T2) — a second lookup by coordinates rather than
    carrying full chunk content in every query response."""
    if not DEFAULT_DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Nothing indexed yet.")
    with Store(DEFAULT_DB_PATH) as store:
        content = store.get_chunk(repo, file_path, start_line, end_line)
    if content is None:
        raise HTTPException(status_code=404, detail="No such citation - the repo may have been reindexed since.")
    return CitationContentResponse(content=content)


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    try:
        config = load_config()
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    embed_client: EmbeddingClient = OllamaEmbeddingClient()
    generator: Generator = ClaudeGenerator()
    try:
        scope = answering.resolve_scope(request.repos, config.repo_names())
        result = answering.answer_question(request.question, scope, request.history, embed_client, generator)
    except answering.AnsweringError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc

    citations = [
        CitationOut(
            index=i,
            repo=c.repo,
            file_path=c.file_path,
            start_line=c.start_line,
            end_line=c.end_line,
            citation=c.citation,
        )
        for i, c in enumerate(result.chunks, start=1)
    ]
    return QueryResponse(answer=result.answer, citations=citations, latency_ms=result.latency_ms)


def main() -> None:  # pragma: no cover - thin wrapper, exercised manually/in T11
    import uvicorn

    uvicorn.run("codebase_rag.api:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
