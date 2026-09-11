"""CLI entrypoint: `codebase-rag index` and `codebase-rag query`.

Two commands cover the whole flow (PRD §7): one to index/reindex a codebase,
one to ask a question, optionally scoped to specific repos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from codebase_rag.chunking import chunk_repo
from codebase_rag.config import load_config
from codebase_rag.embeddings import DEFAULT_MODEL, EmbeddingClient, OllamaEmbeddingClient
from codebase_rag.store import DEFAULT_DB_PATH, Store

app = typer.Typer(
    name="codebase-rag",
    help="Ask grounded, cited questions across every codebase you've indexed.",
    no_args_is_help=True,
)


@app.command()
def index(
    repo: str = typer.Argument(..., help="Name of the repo to index, as listed in config.yaml."),
) -> None:
    """Index (or reindex) one configured codebase (FR-1, FR-3)."""
    config = load_config()
    entry = config.find(repo)
    if entry is None:
        typer.echo(f"'{repo}' isn't in config.yaml. Known repos: {config.repo_names() or 'none configured yet'}")
        raise typer.Exit(code=1)

    root = Path(entry.path)
    if not root.is_dir():
        typer.echo(f"'{entry.path}' isn't a directory - check config.yaml.")
        raise typer.Exit(code=1)

    typer.echo(f"Chunking '{entry.name}' from {entry.path}...")
    chunks = chunk_repo(entry.name, root)
    if not chunks:
        typer.echo("No indexable files found.")
        raise typer.Exit(code=1)
    typer.echo(f"{len(chunks)} chunks. Embedding via Ollama ({DEFAULT_MODEL})...")

    client: EmbeddingClient = OllamaEmbeddingClient()
    try:
        embeddings = client.embed([c.content for c in chunks])
    except Exception as exc:  # Ollama unreachable, model not pulled, etc.
        typer.echo(f"Embedding failed: {exc}")
        raise typer.Exit(code=1) from exc

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Store(DEFAULT_DB_PATH) as store:
        store.replace_repo_chunks(entry.name, chunks, embeddings)

    typer.echo(f"Indexed '{entry.name}': {len(chunks)} chunks -> {DEFAULT_DB_PATH}")


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
        typer.echo("No repos configured yet - run 'codebase-rag index <repo>' first.")
        raise typer.Exit(code=1)

    typer.echo(f"Querying {scope} for: {question!r}")
    typer.echo("(retrieval/generation not implemented yet - see T3)")


if __name__ == "__main__":
    app()
