"""Unit tests for reindexing.py's run_reindex_job (T4 of the v2 PRD, FR-5) —
chunking/embedding success, no-files and embedding failures, and the
cancel-at-checkpoint behavior that makes cancellation safe by construction
(§10 Q12: replace_repo_chunks only ever runs on the uncancelled success path).
"""

from pathlib import Path

from codebase_rag.reindexing import run_reindex_job
from codebase_rag.store import Store


class _FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


class _FailingEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("Failed to connect to Ollama.")


def _write_files(root: Path, count: int) -> None:
    root.mkdir()
    for i in range(count):
        (root / f"f{i}.py").write_text(f"x = {i}", encoding="utf-8")


def test_run_reindex_job_success_persists_chunks_and_marks_done(tmp_path: Path):
    repo_dir = tmp_path / "demo-repo"
    _write_files(repo_dir, 3)
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")

    run_reindex_job(job_id, "demo", repo_dir, db_path, _FakeEmbeddingClient())

    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "done"
        assert job.total_chunks == 3
        assert job.embedded_chunks == 3
        assert job.error is None
        assert store.indexed_repos() == ["demo"]


def test_run_reindex_job_no_indexable_files_fails_cleanly_without_touching_chunks(tmp_path: Path):
    repo_dir = tmp_path / "empty-repo"
    repo_dir.mkdir()
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")

    run_reindex_job(job_id, "demo", repo_dir, db_path, _FakeEmbeddingClient())

    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "failed"
        assert "No indexable files found" in job.error
        assert store.indexed_repos() == []


def test_run_reindex_job_embedding_failure_marks_job_failed(tmp_path: Path):
    repo_dir = tmp_path / "demo-repo"
    _write_files(repo_dir, 2)
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")

    run_reindex_job(job_id, "demo", repo_dir, db_path, _FailingEmbeddingClient())

    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "failed"
        assert "Failed to connect to Ollama" in job.error
        assert store.indexed_repos() == []


def test_run_reindex_job_cancelled_before_it_starts_touches_nothing(tmp_path: Path):
    repo_dir = tmp_path / "demo-repo"
    _write_files(repo_dir, 3)
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")
        store.request_job_cancel(job_id)

    run_reindex_job(job_id, "demo", repo_dir, db_path, _FakeEmbeddingClient())

    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "cancelled"
        assert store.indexed_repos() == []  # replace_repo_chunks never ran


def test_run_reindex_job_cancelled_mid_run_stops_at_the_next_checkpoint(tmp_path: Path, monkeypatch):
    """Spans two embedding batches; the fake client requests cancellation as
    a side effect of the FIRST batch's embed() call, simulating someone
    cancelling while that batch is in flight. The second batch's checkpoint
    must see it and stop before ever calling replace_repo_chunks."""
    import codebase_rag.reindexing as reindexing_module

    monkeypatch.setattr(reindexing_module, "EMBED_BATCH_SIZE", 2)

    repo_dir = tmp_path / "demo-repo"
    _write_files(repo_dir, 5)  # 3 batches of size 2: 2, 2, 1
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")

    class _CancelMidRunEmbeddingClient:
        def __init__(self):
            self.calls = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls += 1
            if self.calls == 1:
                with Store(db_path) as store:
                    store.request_job_cancel(job_id)
            return [[float(len(t)), 0.0] for t in texts]

    client = _CancelMidRunEmbeddingClient()
    run_reindex_job(job_id, "demo", repo_dir, db_path, client)

    assert client.calls == 1  # never reached the second batch
    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "cancelled"
        assert job.embedded_chunks == 2  # progress from the one batch that did run
        assert store.indexed_repos() == []  # index left untouched, per §10 Q12


def test_run_reindex_job_cancelled_during_the_only_batch_stops_before_the_swap(tmp_path: Path):
    """A single-batch run (no in-loop checkpoint left to catch it) still
    must not swap the index - the checkpoint right before replace_repo_chunks
    is what catches a cancel requested during the very last batch."""
    repo_dir = tmp_path / "demo-repo"
    _write_files(repo_dir, 2)  # one batch, well under EMBED_BATCH_SIZE
    db_path = tmp_path / "index.db"

    with Store(db_path) as store:
        job_id = store.create_job("demo")

    class _CancelDuringTheOnlyBatchClient:
        def embed(self, texts: list[str]) -> list[list[float]]:
            with Store(db_path) as store:
                store.request_job_cancel(job_id)
            return [[float(len(t)), 0.0] for t in texts]

    run_reindex_job(job_id, "demo", repo_dir, db_path, _CancelDuringTheOnlyBatchClient())

    with Store(db_path) as store:
        job = store.get_job(job_id)
        assert job.status == "cancelled"
        assert job.embedded_chunks == 2  # the batch itself did complete
        assert store.indexed_repos() == []  # but the swap never happened
