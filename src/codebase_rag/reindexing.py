"""Background reindex jobs (T4 of the v2 dashboard PRD, FR-5).

`run_reindex_job` is the worker the API schedules in the background so a
trigger request returns immediately (§10 Q2): chunk the repo, embed in
batches, checking for a cancel request at each batch boundary (§10 Q11's
"already reindexing" rejection happens earlier, at `Store.create_job` —
this module only runs once a job has already been accepted).

Cancellation is safe by construction (§10 Q12): `replace_repo_chunks` — the
one place the previous index is actually replaced — is only ever called on
the success path, after every batch has embedded and one final checkpoint
has passed. A cancelled or failed run never reaches it, so the existing
index is never left partially overwritten.
"""

from __future__ import annotations

from pathlib import Path

from codebase_rag.chunking import chunk_repo
from codebase_rag.embeddings import EmbeddingClient
from codebase_rag.store import Store

EMBED_BATCH_SIZE = 20  # matches cli.py's `index` command


def run_reindex_job(job_id: int, repo: str, root: Path, db_path: Path, embed_client: EmbeddingClient) -> None:
    """Runs synchronously — the caller (api.py) is responsible for running
    this off the request-handling path (FastAPI `BackgroundTasks`); tests
    call it directly. Opens its own `Store` connection, so it's safe to run
    on a different thread than the one that scheduled it."""
    with Store(db_path) as store:
        try:
            chunks = chunk_repo(repo, root)
            store.set_job_total(job_id, len(chunks))

            if not chunks:
                store.finish_job(job_id, status="failed", error="No indexable files found.")
                return

            embeddings: list[list[float]] = []
            for start in range(0, len(chunks), EMBED_BATCH_SIZE):
                if store.is_job_cancel_requested(job_id):
                    store.finish_job(job_id, status="cancelled")
                    return
                batch = chunks[start : start + EMBED_BATCH_SIZE]
                embeddings.extend(embed_client.embed([c.content for c in batch]))
                store.update_job_progress(job_id, len(embeddings))

            # One more checkpoint right before the atomic swap — a cancel
            # requested during the final batch must still win over it.
            if store.is_job_cancel_requested(job_id):
                store.finish_job(job_id, status="cancelled")
                return

            store.replace_repo_chunks(repo, chunks, embeddings)
            store.finish_job(job_id, status="done")
        except Exception as exc:  # Ollama unreachable, model not pulled, etc.
            store.finish_job(job_id, status="failed", error=str(exc))
