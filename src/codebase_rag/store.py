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
"""


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

    def indexed_repos(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT repo FROM chunks ORDER BY repo").fetchall()
        return [r[0] for r in rows]

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
