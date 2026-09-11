"""Unit tests for answering.py — the retrieve-then-generate pipeline shared
by cli.py's `_answer` and the dashboard's api.py (T1 of the v2 PRD).

test_cli.py already exercises this pipeline end-to-end through the CLI
commands; these tests target answer_question()/resolve_scope() directly so
the shared module has its own coverage independent of either caller.
"""

from pathlib import Path

import pytest

from codebase_rag.answering import (
    AnswerResult,
    EmbeddingFailedError,
    GenerationFailedError,
    NoMatchError,
    NothingIndexedError,
    UnindexedRepoError,
    answer_question,
    resolve_scope,
)
from codebase_rag.chunking import Chunk
from codebase_rag.store import Store


class _FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


class _FailingEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("Failed to connect to Ollama.")


class _FakeGenerator:
    def generate(self, question, chunks, history=None):
        prefix = f"[{len(history)} prior turn(s)] " if history else ""
        return f"{prefix}Fake grounded answer to {question!r} using {len(chunks)} chunk(s)."


class _FailingGenerator:
    def generate(self, question, chunks, history=None):
        raise RuntimeError("Claude API unreachable")


def _indexed_store(tmp_path: Path, repo: str = "demo") -> Path:
    db_path = tmp_path / "index.db"
    with Store(db_path) as store:
        chunk = Chunk(repo=repo, file_path="app.py", start_line=1, end_line=1, content="def f(): ...")
        store.replace_repo_chunks(repo, [chunk], [[1.0, 0.0]])
    return db_path


def test_resolve_scope_defaults_to_every_configured_repo():
    assert resolve_scope(None, ["a", "b"]) == ["a", "b"]


def test_resolve_scope_respects_an_explicit_scope():
    assert resolve_scope(["a"], ["a", "b"]) == ["a"]


def test_resolve_scope_raises_when_nothing_is_configured():
    with pytest.raises(NothingIndexedError, match="No repos configured yet"):
        resolve_scope(None, [])


def test_answer_question_raises_when_db_path_does_not_exist(tmp_path: Path):
    with pytest.raises(NothingIndexedError, match="Nothing indexed yet"):
        answer_question(
            "anything",
            ["demo"],
            None,
            _FakeEmbeddingClient(),
            _FakeGenerator(),
            source="test",
            db_path=tmp_path / "missing.db",
        )


def test_answer_question_raises_on_embedding_failure(tmp_path: Path):
    db_path = _indexed_store(tmp_path)
    with pytest.raises(EmbeddingFailedError, match="Failed to connect to Ollama"):
        answer_question("anything", ["demo"], None, _FailingEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path)


def test_answer_question_raises_on_unindexed_repo_in_scope(tmp_path: Path):
    db_path = _indexed_store(tmp_path)
    with pytest.raises(UnindexedRepoError) as exc_info:
        answer_question("anything", ["demo", "other"], None, _FakeEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path)
    assert exc_info.value.repos == ["other"]


def test_answer_question_raises_when_nothing_matches(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    with Store(db_path):
        pass  # creates the schema but indexes nothing
    with pytest.raises(NoMatchError):
        answer_question("anything", [], None, _FakeEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path)


def test_answer_question_raises_on_generation_failure(tmp_path: Path):
    db_path = _indexed_store(tmp_path)
    with pytest.raises(GenerationFailedError, match="Claude API unreachable"):
        answer_question("anything", ["demo"], None, _FakeEmbeddingClient(), _FailingGenerator(), source="test", db_path=db_path)


def test_answer_question_returns_answer_and_citations(tmp_path: Path):
    db_path = _indexed_store(tmp_path)

    result = answer_question("how does f work?", ["demo"], None, _FakeEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path)

    assert isinstance(result, AnswerResult)
    assert "Fake grounded answer" in result.answer
    assert len(result.chunks) == 1
    assert result.chunks[0].citation == "demo/app.py:1-1"
    assert result.latency_ms >= 0


def test_answer_question_folds_prior_turn_into_retrieval_and_generation(tmp_path: Path):
    db_path = _indexed_store(tmp_path)
    history = [("first question", "first answer")]

    result = answer_question(
        "follow-up", ["demo"], history, _FakeEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path
    )

    assert "[1 prior turn(s)]" in result.answer


def test_answer_question_logs_the_query(tmp_path: Path):
    db_path = _indexed_store(tmp_path)

    answer_question("anything", ["demo"], None, _FakeEmbeddingClient(), _FakeGenerator(), source="test", db_path=db_path)

    with Store(db_path) as store:
        from datetime import datetime, timedelta, timezone

        assert store.queries_since(datetime.now(timezone.utc) - timedelta(minutes=1)) == 1


def test_answer_question_logs_the_answer_and_source(tmp_path: Path):
    db_path = _indexed_store(tmp_path)

    answer_question(
        "anything", ["demo"], None, _FakeEmbeddingClient(), _FakeGenerator(), source="cli", db_path=db_path
    )

    with Store(db_path) as store:
        [logged] = store.recent_queries(limit=1)
        assert logged.source == "cli"
        assert "Fake grounded answer" in logged.answer
