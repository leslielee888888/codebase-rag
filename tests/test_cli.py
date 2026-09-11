"""T1 acceptance checks (CLI skeleton) plus T2's end-to-end `index` command."""

from pathlib import Path

from typer.testing import CliRunner

import codebase_rag.cli as cli_module
from codebase_rag.cli import app

runner = CliRunner()


def test_help_lists_both_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.output
    assert "query" in result.output


def test_index_unknown_repo_errors_cleanly():
    result = runner.invoke(app, ["index", "nonexistent-repo"])
    assert result.exit_code == 1
    assert "nonexistent-repo" in result.output


def test_query_with_no_repos_configured_errors_cleanly():
    result = runner.invoke(app, ["query", "how does this work?"])
    assert result.exit_code == 1
    assert "index" in result.output.lower()


class _FakeEmbeddingClient:
    """Deterministic, network-free stand-in for OllamaEmbeddingClient (FR-1)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


def test_index_command_chunks_embeds_and_persists(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["index", "demo"])

    assert result.exit_code == 0, result.output
    assert "Indexed 'demo'" in result.output
    assert (tmp_path / "data" / "index.db").exists()


def test_reindex_drops_stale_entries(tmp_path: Path, monkeypatch):
    """FR-3: running `index` again on a changed repo is the reindex — stale
    entries for deleted/renamed files are removed, not left dangling."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    old_file = repo_dir / "old.py"
    old_file.write_text("def old(): ...", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )

    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    # the repo changes: old.py is renamed to new.py
    old_file.unlink()
    (repo_dir / "new.py").write_text("def new(): ...", encoding="utf-8")

    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    from codebase_rag.store import DEFAULT_DB_PATH, Store

    with Store(DEFAULT_DB_PATH) as store:
        rows = store.search(query_vector=[0.0, 0.0], top_k=10)

    file_paths = {row[2] for row in rows}
    assert file_paths == {"new.py"}


class _FakeGenerator:
    """Deterministic, network-free stand-in for ClaudeGenerator (FR-2)."""

    def generate(self, question, chunks):
        return f"Fake grounded answer to {question!r} using {len(chunks)} chunk(s)."


def test_query_command_retrieves_and_generates_with_citations(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(cli_module, "ClaudeGenerator", _FakeGenerator)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("def export_package(): ...", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )
    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    result = runner.invoke(app, ["query", "how does the export builder work?"])

    assert result.exit_code == 0, result.output
    assert "Fake grounded answer" in result.output
    assert "Sources:" in result.output
    assert "demo/app.py:1-1" in result.output


def test_query_command_scopes_across_multiple_repos(tmp_path: Path, monkeypatch):
    """FR-5: scope to one, several, or all indexed repos, and retrieval respects it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(cli_module, "ClaudeGenerator", _FakeGenerator)

    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / "a.py").write_text("def alpha(): ...", encoding="utf-8")
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    (repo_b / "b.py").write_text("def beta(): ...", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n"
        f"  - name: repo-a\n    path: {repo_a.as_posix()}\n"
        f"  - name: repo-b\n    path: {repo_b.as_posix()}\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["index", "repo-a"]).exit_code == 0
    assert runner.invoke(app, ["index", "repo-b"]).exit_code == 0

    # scoped to one repo: only that repo's citation shows up
    scoped = runner.invoke(app, ["query", "how does this work?", "--repo", "repo-a"])
    assert scoped.exit_code == 0, scoped.output
    assert "repo-a/a.py" in scoped.output
    assert "repo-b/b.py" not in scoped.output

    # no --repo: defaults to every indexed repo
    all_repos = runner.invoke(app, ["query", "how does this work?"])
    assert all_repos.exit_code == 0, all_repos.output
    assert "repo-a/a.py" in all_repos.output
    assert "repo-b/b.py" in all_repos.output


def test_query_show_prints_the_exact_snippet_behind_a_citation(tmp_path: Path, monkeypatch):
    """FR-4: --show <n> shows the real retrieved content, not just a file link."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(cli_module, "ClaudeGenerator", _FakeGenerator)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("def export_package():\n    return build_zip()", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )
    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    result = runner.invoke(app, ["query", "how does export work?", "--show", "1"])

    assert result.exit_code == 0, result.output
    assert "[1] demo/app.py:1-2" in result.output
    assert "def export_package():" in result.output
    assert "return build_zip()" in result.output


def test_query_show_out_of_range_reports_cleanly_without_failing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)
    monkeypatch.setattr(cli_module, "ClaudeGenerator", _FakeGenerator)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n", encoding="utf-8"
    )
    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    result = runner.invoke(app, ["query", "anything", "--show", "99"])

    assert result.exit_code == 0
    assert "no such citation" in result.output


def test_query_command_scoped_to_unindexed_repo_errors_cleanly(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingClient", _FakeEmbeddingClient)

    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        f"repos:\n  - name: demo\n    path: {repo_dir.as_posix()}\n  - name: other\n    path: {repo_dir.as_posix()}\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["index", "demo"]).exit_code == 0

    result = runner.invoke(app, ["query", "anything", "--repo", "other"])

    assert result.exit_code == 1
    assert "other" in result.output
