"""Unit tests for store.py — a real temp-file SQLite DB, no network."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from codebase_rag.chunking import Chunk
from codebase_rag.store import JobAlreadyRunningError, Store, _cosine


def _chunk(repo: str, file_path: str, content: str) -> Chunk:
    return Chunk(repo=repo, file_path=file_path, start_line=1, end_line=1, content=content)


def test_replace_and_search_round_trip(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        chunks = [_chunk("demo", "a.py", "alpha"), _chunk("demo", "b.py", "beta")]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        store.replace_repo_chunks("demo", chunks, embeddings)

        results = store.search(query_vector=[1.0, 0.0, 0.0], top_k=2)

        assert len(results) == 2
        best = results[0]
        assert best[1] == "demo"
        assert best[2] == "a.py"  # closest to the query vector
        assert best[0] > results[1][0]  # best match ranked first


def test_search_respects_repo_scope(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("repo-a", [_chunk("repo-a", "x.py", "x")], [[1.0, 0.0]])
        store.replace_repo_chunks("repo-b", [_chunk("repo-b", "y.py", "y")], [[1.0, 0.0]])

        scoped = store.search(query_vector=[1.0, 0.0], repos=["repo-a"], top_k=10)

        assert {row[1] for row in scoped} == {"repo-a"}


def test_replace_repo_chunks_drops_stale_entries(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("demo", [_chunk("demo", "old.py", "old")], [[1.0, 0.0]])
        # reindex: old.py was deleted from the repo, new.py added
        store.replace_repo_chunks("demo", [_chunk("demo", "new.py", "new")], [[1.0, 0.0]])

        results = store.search(query_vector=[1.0, 0.0], top_k=10)

        assert {row[2] for row in results} == {"new.py"}


def test_get_chunk_returns_content_for_exact_coordinates(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("demo", [_chunk("demo", "a.py", "alpha")], [[1.0, 0.0]])

        content = store.get_chunk("demo", "a.py", start_line=1, end_line=1)

        assert content == "alpha"


def test_get_chunk_returns_none_when_no_chunk_matches(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("demo", [_chunk("demo", "a.py", "alpha")], [[1.0, 0.0]])

        # wrong repo, wrong file, and a stale line range all miss cleanly
        assert store.get_chunk("other", "a.py", 1, 1) is None
        assert store.get_chunk("demo", "b.py", 1, 1) is None
        assert store.get_chunk("demo", "a.py", 5, 9) is None


def test_indexed_repos_lists_distinct_repos(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("repo-a", [_chunk("repo-a", "x.py", "x")], [[1.0]])
        store.replace_repo_chunks("repo-b", [_chunk("repo-b", "y.py", "y")], [[1.0]])

        assert store.indexed_repos() == ["repo-a", "repo-b"]


def test_repo_status_maps_each_repo_to_its_last_indexed_at(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("repo-a", [_chunk("repo-a", "x.py", "x")], [[1.0]])
        store.replace_repo_chunks("repo-b", [_chunk("repo-b", "y.py", "y")], [[1.0]])

        status = store.repo_status()

        assert set(status.keys()) == {"repo-a", "repo-b"}
        assert all(isinstance(ts, str) and ts for ts in status.values())


def test_repo_status_reflects_a_reindex_not_the_original_index_time(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("demo", [_chunk("demo", "a.py", "v1")], [[1.0]])
        first = store.repo_status()["demo"]

        store.replace_repo_chunks("demo", [_chunk("demo", "a.py", "v2")], [[1.0]])
        second = store.repo_status()["demo"]

        assert second >= first  # ISO 8601 timestamps sort lexicographically


def test_repo_status_is_empty_when_nothing_is_indexed(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        assert store.repo_status() == {}


def test_log_query_and_queries_since_count_recent_queries(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.log_query("how does X work?", ["demo"], num_results=3, latency_ms=120)
        store.log_query("what about Y?", ["demo", "other"], num_results=5, latency_ms=340)

        last_week = store.queries_since(datetime.now(timezone.utc) - timedelta(days=7))
        assert last_week == 2

        # nothing should count as "since" a moment in the future
        future = store.queries_since(datetime.now(timezone.utc) + timedelta(days=1))
        assert future == 0


def test_cosine_with_precomputed_norm_matches_computing_it_internally():
    """search() hoists the query vector's norm out of the per-row loop —
    prove that shortcut gives the exact same answer as computing it fresh."""
    a = [3.0, 4.0, 0.0]  # norm 5
    b = [1.0, 0.0, 0.0]

    computed = _cosine(a, b)
    precomputed = _cosine(a, b, norm_a=5.0)

    assert computed == precomputed


def test_cosine_zero_vector_returns_zero_not_a_division_error():
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert _cosine([1.0, 1.0], [0.0, 0.0]) == 0.0
    assert _cosine([1.0, 1.0], [0.0, 0.0], norm_a=0.0) == 0.0


def test_create_job_then_get_job_round_trips(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        job_id = store.create_job("demo")

        job = store.get_job(job_id)

        assert job.repo == "demo"
        assert job.status == "running"
        assert job.total_chunks is None
        assert job.embedded_chunks == 0
        assert job.cancel_requested is False
        assert job.error is None
        assert job.finished_at is None


def test_create_job_rejects_a_second_running_job_for_the_same_repo(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.create_job("demo")

        with pytest.raises(JobAlreadyRunningError, match="demo"):
            store.create_job("demo")


def test_create_job_allows_a_new_job_once_the_previous_one_finished(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        first = store.create_job("demo")
        store.finish_job(first, status="done")

        second = store.create_job("demo")  # must not raise

        assert second != first


def test_create_job_allows_concurrent_jobs_for_different_repos(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.create_job("repo-a")
        store.create_job("repo-b")  # must not raise


def test_set_job_total_and_update_job_progress(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        job_id = store.create_job("demo")
        store.set_job_total(job_id, 42)
        store.update_job_progress(job_id, 17)

        job = store.get_job(job_id)

        assert job.total_chunks == 42
        assert job.embedded_chunks == 17


def test_request_job_cancel_sets_the_flag_only_on_a_running_job(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        running = store.create_job("demo")
        store.request_job_cancel(running)
        assert store.is_job_cancel_requested(running) is True

        finished = store.create_job("other")
        store.finish_job(finished, status="done")
        store.request_job_cancel(finished)  # no-op: not running
        assert store.is_job_cancel_requested(finished) is False


def test_finish_job_records_status_error_and_finished_at(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        job_id = store.create_job("demo")

        store.finish_job(job_id, status="failed", error="Embedding failed: boom")

        job = store.get_job(job_id)
        assert job.status == "failed"
        assert job.error == "Embedding failed: boom"
        assert job.finished_at is not None


def test_finish_job_frees_up_the_repo_for_a_new_job(tmp_path: Path):
    """The partial unique index only guards 'running' rows - once a job is
    finished, a new one for the same repo must be allowed (see also
    test_create_job_allows_a_new_job_once_the_previous_one_finished, which
    checks this from create_job's side)."""
    with Store(tmp_path / "index.db") as store:
        job_id = store.create_job("demo")
        store.finish_job(job_id, status="cancelled")

        store.create_job("demo")  # must not raise


def test_latest_job_for_repo_returns_the_most_recent_one(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        first = store.create_job("demo")
        store.finish_job(first, status="done")
        second = store.create_job("demo")

        latest = store.latest_job_for_repo("demo")

        assert latest.id == second


def test_latest_job_for_repo_returns_none_when_no_job_ever_ran(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        assert store.latest_job_for_repo("never-indexed") is None


def test_get_job_returns_none_for_an_unknown_id(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        assert store.get_job(999) is None


def test_search_top_k_truncates_to_the_best_matches(tmp_path: Path):
    """The scored[:top_k] slice that actually caps results — exercised with
    more matches than top_k, not just exactly top_k or fewer."""
    with Store(tmp_path / "index.db") as store:
        chunks = [_chunk("demo", f"f{i}.py", str(i)) for i in range(5)]
        # similarity to [1, 0] increases with i via the x-component
        embeddings = [[float(i), 1.0] for i in range(5)]
        store.replace_repo_chunks("demo", chunks, embeddings)

        results = store.search(query_vector=[1.0, 0.0], top_k=2)

        assert len(results) == 2
        assert [r[2] for r in results] == ["f4.py", "f3.py"]
