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
