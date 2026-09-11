"""Unit tests for store.py — a real temp-file SQLite DB, no network."""

from pathlib import Path

from codebase_rag.chunking import Chunk
from codebase_rag.store import Store


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


def test_indexed_repos_lists_distinct_repos(tmp_path: Path):
    with Store(tmp_path / "index.db") as store:
        store.replace_repo_chunks("repo-a", [_chunk("repo-a", "x.py", "x")], [[1.0]])
        store.replace_repo_chunks("repo-b", [_chunk("repo-b", "y.py", "y")], [[1.0]])

        assert store.indexed_repos() == ["repo-a", "repo-b"]
