"""T1 acceptance checks: the dashboard's `POST /query` endpoint (FR-1, FR-2,
FR-6) and `GET /health`. Mirrors test_cli.py's fakes/patterns so the two
surfaces stay directly comparable — both call the same `answering` pipeline.
"""

from pathlib import Path

from fastapi.testclient import TestClient

import codebase_rag.api as api_module
from codebase_rag.api import app

client = TestClient(app)


class _FakeEmbeddingClient:
    """Deterministic, network-free stand-in for OllamaEmbeddingClient."""

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


def _index_one_repo(tmp_path: Path, monkeypatch, repo: str = "demo") -> None:
    """Same shape as test_cli.py's indexing setup, via the real `index`
    CLI command so this exercises the actual on-disk config.yaml/index.db
    the API also reads — not a hand-built fixture."""
    from typer.testing import CliRunner

    import codebase_rag.cli as cli_module
    from codebase_rag.cli import app as cli_app

    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)

    repo_dir = tmp_path / f"{repo}-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("def export_package(): ...", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: {repo}\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )

    result = CliRunner().invoke(cli_app, ["index", repo])
    assert result.exit_code == 0, result.output


def test_health_reports_ok():
    result = client.get("/health")

    assert result.status_code == 200
    assert result.json() == {"status": "ok"}


def test_query_with_no_repos_configured_returns_409(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.post("/query", json={"question": "anything"})

    assert result.status_code == 409
    assert "configured" in result.json()["detail"].lower()


def test_query_malformed_config_yaml_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    result = client.post("/query", json={"question": "anything"})

    assert result.status_code == 400
    assert "is missing name" in result.json()["detail"]


def test_query_returns_grounded_answer_with_citations(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    result = client.post("/query", json={"question": "how does export work?"})

    assert result.status_code == 200, result.text
    body = result.json()
    assert "Fake grounded answer" in body["answer"]
    assert body["citations"] == [
        {
            "index": 1,
            "repo": "demo",
            "file_path": "app.py",
            "start_line": 1,
            "end_line": 1,
            "citation": "demo/app.py:1-1",
        }
    ]
    assert body["latency_ms"] >= 0


def test_query_scoped_to_one_repo_excludes_the_other(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch, repo="repo-a")
    _index_one_repo(tmp_path, monkeypatch, repo="repo-b")
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    result = client.post("/query", json={"question": "how does this work?", "repos": ["repo-a"]})

    assert result.status_code == 200, result.text
    repos_cited = {c["repo"] for c in result.json()["citations"]}
    assert repos_cited == {"repo-a"}


def test_query_scoped_to_an_unindexed_repo_returns_409(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    (tmp_path / "config.yaml").write_text(
        "repos:\n  - name: demo\n    path: .\n  - name: other\n    path: .\n", encoding="utf-8"
    )
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    result = client.post("/query", json={"question": "anything", "repos": ["other"]})

    assert result.status_code == 409
    assert "other" in result.json()["detail"]


def test_query_folds_prior_turn_into_the_generator_call(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    result = client.post(
        "/query",
        json={"question": "follow-up", "history": [["first question", "first answer"]]},
    )

    assert result.status_code == 200, result.text
    assert "[1 prior turn(s)]" in result.json()["answer"]


def test_query_embedding_failure_returns_502(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FailingEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    result = client.post("/query", json={"question": "anything"})

    assert result.status_code == 502
    assert "Failed to connect to Ollama" in result.json()["detail"]


def test_query_generation_failure_returns_502(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FailingGenerator)

    result = client.post("/query", json={"question": "anything"})

    assert result.status_code == 502
    assert "Claude API unreachable" in result.json()["detail"]


def test_query_missing_question_is_rejected_with_422(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.post("/query", json={})

    assert result.status_code == 422


def test_citation_with_nothing_indexed_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.get(
        "/citation", params={"repo": "demo", "file_path": "app.py", "start_line": 1, "end_line": 1}
    )

    assert result.status_code == 404


def test_citation_returns_the_exact_snippet(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)

    result = client.get(
        "/citation", params={"repo": "demo", "file_path": "app.py", "start_line": 1, "end_line": 1}
    )

    assert result.status_code == 200, result.text
    assert result.json() == {"content": "def export_package(): ..."}


def test_citation_with_no_matching_chunk_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)

    result = client.get(
        "/citation", params={"repo": "demo", "file_path": "does-not-exist.py", "start_line": 1, "end_line": 1}
    )

    assert result.status_code == 404


def test_repos_with_nothing_configured_returns_empty_list(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.get("/repos")

    assert result.status_code == 200, result.text
    assert result.json() == {"repos": []}


def test_repos_malformed_config_yaml_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    result = client.get("/repos")

    assert result.status_code == 400
    assert "is missing name" in result.json()["detail"]


def test_repos_lists_configured_repos_with_indexed_state_and_timestamp(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch, repo="demo")
    # a second repo configured but never indexed (FR-4: still listed)
    (tmp_path / "config.yaml").write_text(
        (tmp_path / "config.yaml").read_text(encoding="utf-8")
        + "  - name: unindexed\n    path: /repos/unindexed\n",
        encoding="utf-8",
    )

    result = client.get("/repos")

    assert result.status_code == 200, result.text
    by_name = {r["name"]: r for r in result.json()["repos"]}
    assert set(by_name) == {"demo", "unindexed"}
    assert by_name["demo"]["indexed"] is True
    assert by_name["demo"]["last_indexed_at"]  # a real timestamp, not None
    assert by_name["unindexed"]["indexed"] is False
    assert by_name["unindexed"]["last_indexed_at"] is None
