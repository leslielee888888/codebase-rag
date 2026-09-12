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

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codebase_rag import answering
from codebase_rag.config import Config, ConfigError, RepoEntry, load_config, save_config
from codebase_rag.embeddings import EmbeddingClient, OllamaEmbeddingClient
from codebase_rag.generation import ClaudeGenerator, Generator, Turn
from codebase_rag.reindexing import run_reindex_job
from codebase_rag.store import DEFAULT_DB_PATH, JobAlreadyRunningError, JobRow, Store

app = FastAPI(title="codebase-rag dashboard API", version="0.1.0")

# Guards config.yaml's read-modify-write in add_repo/remove_repo: a plain
# in-process lock is enough for this single-user tool (one API process,
# no multi-worker deployment) and avoids needing file-level locking for
# a race that, here, only two of Leslie's own browser tabs could trigger.
_config_lock = threading.Lock()

# T7 surfaced this: the browser-facing dashboard (web/) calls this API
# client-side (POST /query, GET /citation), which needs CORS regardless of
# what host serves the frontend. Wide open, not an allow-list, matches the
# PRD's already-accepted trust model (§8/§10 Q6: LAN-only, no auth, same as
# every other self-hosted tool here) - there's no session or credential for
# a cross-origin request to steal.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class AddRepoRequest(BaseModel):
    name: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)


class StatsResponse(BaseModel):
    queries_this_week: int
    queries_this_week_by_source: dict[str, int]


class HistoryEntryOut(BaseModel):
    id: int
    asked_at: str
    question: str
    answer: str | None
    source: str
    repos: list[str]


class HistoryResponse(BaseModel):
    entries: list[HistoryEntryOut]


class JobOut(BaseModel):
    job_id: int
    repo: str
    status: str
    total_chunks: int | None = None
    embedded_chunks: int
    cancel_requested: bool
    error: str | None = None

    @classmethod
    def from_row(cls, job: JobRow) -> "JobOut":
        return cls(
            job_id=job.id,
            repo=job.repo,
            status=job.status,
            total_chunks=job.total_chunks,
            embedded_chunks=job.embedded_chunks,
            cancel_requested=job.cancel_requested,
            error=job.error,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Queries/week, split dashboard vs. CLI (§5, T5) — the real,
    queryable signal on whether the dashboard displaced day-to-day CLI
    use."""
    if not DEFAULT_DB_PATH.exists():
        return StatsResponse(queries_this_week=0, queries_this_week_by_source={})
    since = datetime.now(timezone.utc) - timedelta(days=7)
    with Store(DEFAULT_DB_PATH) as store:
        total = store.queries_since(since)
        by_source = store.queries_since_by_source(since)
    return StatsResponse(queries_this_week=total, queries_this_week_by_source=by_source)


@app.get("/history", response_model=HistoryResponse)
def history(limit: int = 20) -> HistoryResponse:
    """Recent questions, each carrying its own stored answer (FR-7, T5) —
    clicking one in the UI shows the real original answer, not just the
    question text."""
    if not DEFAULT_DB_PATH.exists():
        return HistoryResponse(entries=[])
    with Store(DEFAULT_DB_PATH) as store:
        rows = store.recent_queries(limit=limit)
    return HistoryResponse(
        entries=[
            HistoryEntryOut(
                id=r.id, asked_at=r.asked_at, question=r.question, answer=r.answer, source=r.source, repos=r.repos
            )
            for r in rows
        ]
    )


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


@app.post("/repos", response_model=RepoOut, status_code=201)
def add_repo(request: AddRepoRequest) -> RepoOut:
    """Add a repo entry already reachable on the NAS filesystem (FR-8a,
    T6) — a UI-editable equivalent of hand-editing config.yaml, not a
    file-upload feature; the content itself must already be there."""
    with _config_lock:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if config.find(request.name) is not None:
            raise HTTPException(status_code=409, detail=f"'{request.name}' is already configured.")

        updated = Config(repos=[*config.repos, RepoEntry(name=request.name, path=request.path)])
        save_config(updated)

    return RepoOut(name=request.name, path=request.path, indexed=False, last_indexed_at=None)


@app.delete("/repos/{repo}", status_code=204)
def remove_repo(repo: str) -> Response:
    """Remove a repo entry and delete its indexed chunks immediately
    (FR-8b, §10 Q9) — no lingering, unlisted-but-still-searchable content.
    The confirm-before-remove step (§10 Q13) is the frontend's job (T9);
    this endpoint does exactly what it's asked, unconditionally — except
    while a reindex is actively running for it (409): `run_reindex_job`
    doesn't know the repo was removed out from under it, and would
    silently re-insert chunks for a now-unlisted repo via
    `replace_repo_chunks` on its next successful completion. Cancel the
    reindex (or wait for it to finish) first."""
    if DEFAULT_DB_PATH.exists():
        with Store(DEFAULT_DB_PATH) as store:
            job = store.latest_job_for_repo(repo)
        if job is not None and job.status == "running":
            raise HTTPException(
                status_code=409,
                detail=f"'{repo}' is currently reindexing — cancel the reindex before removing it.",
            )

    with _config_lock:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if config.find(repo) is None:
            raise HTTPException(status_code=404, detail=f"'{repo}' isn't in config.yaml.")

        updated = Config(repos=[r for r in config.repos if r.name != repo])
        save_config(updated)

    if DEFAULT_DB_PATH.exists():
        with Store(DEFAULT_DB_PATH) as store:
            store.delete_repo_chunks(repo)

    return Response(status_code=204)


@app.post("/repos/{repo}/reindex", response_model=JobOut, status_code=202)
def trigger_reindex(repo: str, background_tasks: BackgroundTasks) -> JobOut:
    """Enqueue a reindex as a background job (FR-5, T4) — the request
    returns as soon as the job is accepted, not when it finishes (§10 Q2).
    Rejects a repo that's already reindexing (§10 Q11) rather than queueing
    or restarting it."""
    try:
        config = load_config()
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = config.find(repo)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"'{repo}' isn't in config.yaml.")

    root = Path(entry.path)
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"'{entry.path}' isn't a directory - check config.yaml.")

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        try:
            job_id = store.create_job(repo)
        except JobAlreadyRunningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        job = store.get_job(job_id)

    embed_client: EmbeddingClient = OllamaEmbeddingClient()
    background_tasks.add_task(run_reindex_job, job_id, repo, root, DEFAULT_DB_PATH, embed_client)

    return JobOut.from_row(job)


@app.get("/repos/{repo}/reindex", response_model=JobOut)
def reindex_status(repo: str) -> JobOut:
    """The latest reindex job for `repo` — running, or the outcome of the
    most recent one (FR-5)."""
    if not DEFAULT_DB_PATH.exists():
        raise HTTPException(status_code=404, detail=f"No reindex job found for '{repo}'.")
    with Store(DEFAULT_DB_PATH) as store:
        job = store.latest_job_for_repo(repo)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No reindex job found for '{repo}'.")
    return JobOut.from_row(job)


@app.delete("/repos/{repo}/reindex", response_model=JobOut)
def cancel_reindex(repo: str) -> JobOut:
    """Cancel `repo`'s running reindex job (FR-5) — flags it to stop at its
    next checkpoint; the existing index is untouched (§10 Q12)."""
    if not DEFAULT_DB_PATH.exists():
        raise HTTPException(status_code=404, detail=f"No reindex job found for '{repo}'.")
    with Store(DEFAULT_DB_PATH) as store:
        job = store.latest_job_for_repo(repo)
        if job is None or job.status != "running":
            raise HTTPException(status_code=409, detail=f"'{repo}' isn't currently reindexing.")
        store.request_job_cancel(job.id)
        job = store.get_job(job.id)
    return JobOut.from_row(job)


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
        result = answering.answer_question(
            request.question, scope, request.history, embed_client, generator, source="dashboard"
        )
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
