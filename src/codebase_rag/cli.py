"""CLI entrypoint: `codebase-rag index` and `codebase-rag query`.

Two commands cover the whole flow (PRD §7): one to index/reindex a codebase,
one to ask a question, optionally scoped to specific repos. Both are stubs
here — T2 (indexing pipeline) and T3 (query pipeline) give them real bodies.
"""

from __future__ import annotations

from typing import Optional

import typer

from codebase_rag.config import load_config

app = typer.Typer(
    name="codebase-rag",
    help="Ask grounded, cited questions across every codebase you've indexed.",
    no_args_is_help=True,
)


@app.command()
def index(
    repo: str = typer.Argument(..., help="Name of the repo to index, as listed in config.yaml."),
) -> None:
    """Index (or reindex) one configured codebase."""
    config = load_config()
    entry = config.find(repo)
    if entry is None:
        typer.echo(f"'{repo}' isn't in config.yaml. Known repos: {config.repo_names() or 'none configured yet'}")
        raise typer.Exit(code=1)

    typer.echo(f"Indexing '{entry.name}' from {entry.path}...")
    typer.echo("(chunking/embedding/persistence not implemented yet - see T2)")


@app.command()
def query(
    question: str = typer.Argument(..., help="The question to ask."),
    repos: Optional[list[str]] = typer.Option(
        None, "--repo", help="Repo(s) to scope the query to (repeatable). Default: all indexed repos."
    ),
) -> None:
    """Ask a question, grounded in retrieved source with citations."""
    config = load_config()
    scope = repos or config.repo_names()
    if not scope:
        typer.echo("No repos configured yet — run 'codebase-rag index <repo>' first.")
        raise typer.Exit(code=1)

    typer.echo(f"Querying {scope} for: {question!r}")
    typer.echo("(retrieval/generation not implemented yet - see T3)")


if __name__ == "__main__":
    app()
