"""T1 acceptance checks: the CLI skeleton exists with working stub commands."""

from typer.testing import CliRunner

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
