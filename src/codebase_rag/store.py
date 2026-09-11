"""SQLite storage for indexed chunks (§10 Q3 — no vector extension).

Combined source across Leslie's repos is ~15MB (low thousands of chunks),
so brute-force cosine similarity over SQL-filtered rows is fast enough —
there's no ANN index here on purpose. `search()` does a `WHERE repo IN (...)`
to scope a query (FR-5), then ranks the returned rows in Python.
"""

from __future__ import annotations

import math
import sqlite3
from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from codebase_rag.chunking import Chunk

DEFAULT_DB_PATH = Path("data/index.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repo);
CREATE INDEX IF NOT EXISTS idx_chunks_repo_file ON chunks(repo, file_path);

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asked_at TEXT NOT NULL,
    question TEXT NOT NULL,
    repos TEXT NOT NULL,
    num_results INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_query_log_asked_at ON query_log(asked_at);

-- Background reindex jobs (T4 of the v2 dashboard PRD, FR-5). The partial
-- unique index is what makes "reject a duplicate trigger" (§10 Q11) an
-- atomic, race-free DB constraint rather than an app-level check-then-insert:
-- a second INSERT for a repo that already has a 'running' row fails with
-- sqlite3.IntegrityError, which create_job() turns into JobAlreadyRunningError.
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running' | 'done' | 'failed' | 'cancelled'
    total_chunks INTEGER,
    embedded_chunks INTEGER NOT NULL DEFAULT 0,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_one_running_per_repo ON jobs(repo) WHERE status = 'running';
"""


class JobAlreadyRunningError(ValueError):
    """A reindex job is already running for this repo (§10 Q11)."""


@dataclass(frozen=True)
class JobRow:
    id: int
    repo: str
    status: str
    total_chunks: int | None
    embedded_chunks: int
    cancel_requested: bool
    error: str | None
    started_at: str
    finished_at: str | None


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    a = array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: list[float], b: list[float], norm_a: float | None = None) -> float:
    """Cosine similarity. `a` is the query vector — its norm is identical
    across every row `search()` scores, so callers doing a batch of these
    against the same `a` should compute it once and pass it in rather than
    let every call recompute it (this is the dominant cost of a query on
    the NAS's CPU — §10 Q5)."""
    dot = sum(x * y for x, y in zip(a, b))
    if norm_a is None:
        norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class Store:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def replace_repo_chunks(self, repo: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Reindex: drop every existing chunk for `repo`, insert the fresh set.

        Simplest correct reindex strategy for a corpus this size (§10 Q3) —
        no incremental diffing, just recompute and swap. FR-3's "stale
        entries removed or updated" is satisfied by the delete-then-insert.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute("DELETE FROM chunks WHERE repo = ?", (repo,))
            self._conn.executemany(
                """
                INSERT INTO chunks (repo, file_path, start_line, end_line, content, embedding, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (c.repo, c.file_path, c.start_line, c.end_line, c.content, _to_blob(vec), now)
                    for c, vec in zip(chunks, embeddings)
                ],
            )

    def get_chunk(self, repo: str, file_path: str, start_line: int, end_line: int) -> str | None:
        """Look up one chunk's exact content by its citation coordinates
        (T2 of the dashboard PRD, FR-3) — re-fetches the snippet behind a
        citation the query endpoint already returned, without carrying full
        chunk content in every query response. Returns None if no chunk
        matches (e.g. the repo was reindexed since the citation was given,
        and its boundaries shifted)."""
        row = self._conn.execute(
            "SELECT content FROM chunks WHERE repo = ? AND file_path = ? AND start_line = ? AND end_line = ?",
            (repo, file_path, start_line, end_line),
        ).fetchone()
        return row[0] if row else None

    def indexed_repos(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT repo FROM chunks ORDER BY repo").fetchall()
        return [r[0] for r in rows]

    def repo_status(self) -> dict[str, str]:
        """Every indexed repo's most recent `indexed_at` (ISO 8601), as a
        repo -> timestamp mapping (T3 of the dashboard PRD, FR-4). Every
        chunk from one `replace_repo_chunks` call shares the same
        `indexed_at`, so `MAX` here is just "this repo's last reindex",
        not an aggregate over meaningfully different values."""
        rows = self._conn.execute("SELECT repo, MAX(indexed_at) FROM chunks GROUP BY repo").fetchall()
        return {repo: indexed_at for repo, indexed_at in rows}

    def search(
        self, query_vector: list[float], repos: list[str] | None = None, top_k: int = 8
    ) -> list[tuple[float, str, str, int, int, str]]:
        """Return up to `top_k` (similarity, repo, file_path, start_line, end_line, content),
        best match first, optionally scoped to `repos` (FR-5)."""
        if repos:
            placeholders = ",".join("?" for _ in repos)
            rows = self._conn.execute(
                f"SELECT repo, file_path, start_line, end_line, content, embedding "
                f"FROM chunks WHERE repo IN ({placeholders})",
                repos,
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT repo, file_path, start_line, end_line, content, embedding FROM chunks"
            ).fetchall()

        query_norm = math.sqrt(sum(x * x for x in query_vector))
        scored = [
            (
                _cosine(query_vector, _from_blob(embedding), norm_a=query_norm),
                repo,
                file_path,
                start_line,
                end_line,
                content,
            )
            for repo, file_path, start_line, end_line, content, embedding in rows
        ]
        scored.sort(key=lambda row: row[0], reverse=True)
        return scored[:top_k]

    def log_query(self, question: str, repos: list[str], num_results: int, latency_ms: int) -> None:
        """Record one query (§5/§9) — every query, its scope, result count, and
        latency, so 'queries/week' is a count over this table, not separate
        instrumentation."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO query_log (asked_at, question, repos, num_results, latency_ms) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), question, ",".join(repos), num_results, latency_ms),
            )

    def queries_since(self, since: datetime) -> int:
        """Count of queries logged at or after `since` — the §5 queries/week metric
        is `queries_since(datetime.now(timezone.utc) - timedelta(days=7))`."""
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM query_log WHERE asked_at >= ?", (since.isoformat(),)
        ).fetchone()
        return count

    def create_job(self, repo: str) -> int:
        """Start tracking a new reindex job for `repo`. Raises
        `JobAlreadyRunningError` if one is already running for it — see the
        schema's partial unique index above for why this can't race."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "INSERT INTO jobs (repo, status, embedded_chunks, cancel_requested, started_at) "
                    "VALUES (?, 'running', 0, 0, ?)",
                    (repo, now),
                )
        except sqlite3.IntegrityError as exc:
            raise JobAlreadyRunningError(f"'{repo}' is already reindexing.") from exc
        return cursor.lastrowid

    def set_job_total(self, job_id: int, total_chunks: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE jobs SET total_chunks = ? WHERE id = ?", (total_chunks, job_id))

    def update_job_progress(self, job_id: int, embedded_chunks: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE jobs SET embedded_chunks = ? WHERE id = ?", (embedded_chunks, job_id))

    def request_job_cancel(self, job_id: int) -> None:
        """Flag a running job to stop at its next checkpoint (§10 Q12). A
        no-op if the job isn't running (already finished, or doesn't exist)."""
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET cancel_requested = 1 WHERE id = ? AND status = 'running'", (job_id,)
            )

    def is_job_cancel_requested(self, job_id: int) -> bool:
        row = self._conn.execute("SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return bool(row and row[0])

    def finish_job(self, job_id: int, status: str, error: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ?, finished_at = ? WHERE id = ?",
                (status, error, now, job_id),
            )

    _JOB_COLUMNS = (
        "id, repo, status, total_chunks, embedded_chunks, cancel_requested, error, started_at, finished_at"
    )

    def _row_to_job(self, row: tuple) -> JobRow:
        id_, repo, status, total, embedded, cancel_requested, error, started_at, finished_at = row
        return JobRow(id_, repo, status, total, embedded, bool(cancel_requested), error, started_at, finished_at)

    def get_job(self, job_id: int) -> JobRow | None:
        row = self._conn.execute(f"SELECT {self._JOB_COLUMNS} FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def latest_job_for_repo(self, repo: str) -> JobRow | None:
        """The most recently created job for `repo`, if any — since only one
        job can ever be 'running' for a repo at a time (the schema's partial
        unique index), this is also the currently-running one whenever one
        exists."""
        row = self._conn.execute(
            f"SELECT {self._JOB_COLUMNS} FROM jobs WHERE repo = ? ORDER BY id DESC LIMIT 1", (repo,)
        ).fetchone()
        return self._row_to_job(row) if row else None
