"""T1 acceptance checks: the dashboard's `POST /query` endpoint (FR-1, FR-2,
FR-6) and `GET /health`. Mirrors test_cli.py's fakes/patterns so the two
surfaces stay directly comparable — both call the same `answering` pipeline.
"""

from pathlib import Path

from fastapi.testclient import TestClient

import codebase_rag.api as api_module
from codebase_rag.api import app
from codebase_rag.store import DEFAULT_DB_PATH, Store

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


def test_cors_allows_a_browser_origin_to_call_the_api():
    """T7 surfaced this: the dashboard frontend calls this API client-side
    from its own origin, which needs CORS regardless of deployment host."""
    result = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert result.status_code == 200
    assert result.headers["access-control-allow-origin"] == "*"


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


def _configure_repo(tmp_path: Path, name: str = "demo", file_count: int = 3) -> Path:
    """A repo entry in config.yaml with real files on disk, but NOT yet
    indexed - the reindex endpoints are the ones expected to do that."""
    repo_dir = tmp_path / f"{name}-repo"
    repo_dir.mkdir()
    for i in range(file_count):
        (repo_dir / f"f{i}.py").write_text(f"x = {i}", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else "repos:\n"
    config_path.write_text(existing + f"  - name: {name}\n    path: {repo_dir.as_posix()}\n", encoding="utf-8")
    return repo_dir


def test_trigger_reindex_malformed_config_yaml_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    result = client.post("/repos/demo/reindex")

    assert result.status_code == 400
    assert "is missing name" in result.json()["detail"]


def test_reindex_status_db_exists_but_no_job_for_this_repo_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        store.create_job("other-repo")

    result = client.get("/repos/demo/reindex")

    assert result.status_code == 404


def test_trigger_reindex_unknown_repo_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.post("/repos/nonexistent/reindex")

    assert result.status_code == 404
    assert "nonexistent" in result.json()["detail"]


def test_trigger_reindex_path_not_a_directory_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "repos:\n  - name: demo\n    path: /does/not/exist\n", encoding="utf-8"
    )

    result = client.post("/repos/demo/reindex")

    assert result.status_code == 400
    assert "isn't a directory" in result.json()["detail"]


def test_trigger_reindex_runs_in_the_background_and_persists_chunks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _configure_repo(tmp_path)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)

    result = client.post("/repos/demo/reindex")

    assert result.status_code == 202, result.text
    body = result.json()
    assert body["repo"] == "demo"
    # TestClient runs the background task inline before returning, so the
    # job has already finished by the time the response comes back.
    status = client.get("/repos/demo/reindex")
    assert status.status_code == 200, status.text
    job = status.json()
    assert job["status"] == "done"
    assert job["total_chunks"] == 3
    assert job["embedded_chunks"] == 3

    repos_result = client.get("/repos")
    assert repos_result.json()["repos"][0]["indexed"] is True


def test_trigger_reindex_rejects_a_duplicate_for_a_running_repo(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _configure_repo(tmp_path)
    # seed a still-"running" job directly, since a real trigger through the
    # TestClient completes its background task before returning
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        store.create_job("demo")

    result = client.post("/repos/demo/reindex")

    assert result.status_code == 409
    assert "already reindexing" in result.json()["detail"]


def test_reindex_status_with_no_job_ever_run_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.get("/repos/demo/reindex")

    assert result.status_code == 404


def test_cancel_reindex_with_no_job_ever_run_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.delete("/repos/demo/reindex")

    assert result.status_code == 404


def test_cancel_reindex_when_not_currently_running_returns_409(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        job_id = store.create_job("demo")
        store.finish_job(job_id, status="done")

    result = client.delete("/repos/demo/reindex")

    assert result.status_code == 409
    assert "isn't currently reindexing" in result.json()["detail"]


def test_cancel_reindex_flags_a_running_job(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        store.create_job("demo")

    result = client.delete("/repos/demo/reindex")

    assert result.status_code == 200, result.text
    body = result.json()
    assert body["cancel_requested"] is True
    with Store(DEFAULT_DB_PATH) as store:
        assert store.is_job_cancel_requested(body["job_id"]) is True


def test_stats_with_nothing_indexed_returns_zeros(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.get("/stats")

    assert result.status_code == 200, result.text
    assert result.json() == {"queries_this_week": 0, "queries_this_week_by_source": {}}


def test_stats_splits_queries_by_source(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    assert client.post("/query", json={"question": "from the dashboard"}).status_code == 200
    with Store(DEFAULT_DB_PATH) as store:
        store.log_query("from the cli", ["demo"], num_results=1, latency_ms=1, source="cli")

    result = client.get("/stats")

    assert result.status_code == 200, result.text
    body = result.json()
    assert body["queries_this_week"] == 2
    assert body["queries_this_week_by_source"] == {"dashboard": 1, "cli": 1}


def test_history_with_nothing_logged_returns_empty_list(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.get("/history")

    assert result.status_code == 200, result.text
    assert result.json() == {"entries": []}


def test_history_shows_each_entrys_real_answer(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(api_module, "ClaudeGenerator", _FakeGenerator)

    assert client.post("/query", json={"question": "how does export work?"}).status_code == 200

    result = client.get("/history")

    assert result.status_code == 200, result.text
    [entry] = result.json()["entries"]
    assert entry["question"] == "how does export work?"
    assert "Fake grounded answer" in entry["answer"]
    assert entry["source"] == "dashboard"
    assert entry["repos"] == ["demo"]


def test_history_respects_the_limit_param(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        for i in range(5):
            store.log_query(f"q{i}", ["demo"], num_results=1, latency_ms=1, source="dashboard")

    result = client.get("/history", params={"limit": 2})

    assert result.status_code == 200, result.text
    assert len(result.json()["entries"]) == 2


def test_add_repo_appends_a_new_entry(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.post("/repos", json={"name": "new-repo", "path": "/repos/new-repo"})

    assert result.status_code == 201, result.text
    assert result.json() == {"name": "new-repo", "path": "/repos/new-repo", "indexed": False, "last_indexed_at": None}

    listed = client.get("/repos").json()["repos"]
    assert listed == [{"name": "new-repo", "path": "/repos/new-repo", "indexed": False, "last_indexed_at": None}]


def test_add_repo_rejects_a_duplicate_name(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _configure_repo(tmp_path, name="demo")

    result = client.post("/repos", json={"name": "demo", "path": "/somewhere/else"})

    assert result.status_code == 409
    assert "already configured" in result.json()["detail"]


def test_add_repo_malformed_config_yaml_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    result = client.post("/repos", json={"name": "new-repo", "path": "/x"})

    assert result.status_code == 400
    assert "is missing name" in result.json()["detail"]


def test_add_repo_missing_fields_returns_422(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.post("/repos", json={"name": "new-repo"})

    assert result.status_code == 422


def test_remove_repo_malformed_config_yaml_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    result = client.delete("/repos/demo")

    assert result.status_code == 400
    assert "is missing name" in result.json()["detail"]


def test_remove_repo_unknown_name_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = client.delete("/repos/nonexistent")

    assert result.status_code == 404


def test_remove_repo_deletes_the_config_entry_and_its_chunks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _index_one_repo(tmp_path, monkeypatch)

    result = client.delete("/repos/demo")

    assert result.status_code == 204
    assert client.get("/repos").json()["repos"] == []
    with Store(DEFAULT_DB_PATH) as store:
        assert store.indexed_repos() == []


def test_remove_repo_leaves_other_repos_untouched(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # _index_one_repo overwrites config.yaml with a single entry each call,
    # so restore both afterward - both repos are independently indexed in
    # the DB either way, which is what this test actually exercises.
    _index_one_repo(tmp_path, monkeypatch, repo="repo-a")
    _index_one_repo(tmp_path, monkeypatch, repo="repo-b")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n"
        f"  - name: repo-a\n    path: {(tmp_path / 'repo-a-repo').as_posix()}\n"
        f"  - name: repo-b\n    path: {(tmp_path / 'repo-b-repo').as_posix()}\n",
        encoding="utf-8",
    )

    result = client.delete("/repos/repo-a")

    assert result.status_code == 204
    remaining = {r["name"] for r in client.get("/repos").json()["repos"]}
    assert remaining == {"repo-b"}
    with Store(DEFAULT_DB_PATH) as store:
        assert store.indexed_repos() == ["repo-b"]


def test_remove_repo_never_indexed_still_removes_the_config_entry(tmp_path: Path, monkeypatch):
    """FR-8b applies even when the DB doesn't exist yet at all - removal
    must not require a prior index."""
    monkeypatch.chdir(tmp_path)
    _configure_repo(tmp_path, name="demo")

    result = client.delete("/repos/demo")

    assert result.status_code == 204
    assert client.get("/repos").json()["repos"] == []


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
