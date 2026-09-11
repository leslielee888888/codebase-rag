"""CLI entrypoint: `codebase-rag index` and `codebase-rag query`.

Two commands cover the whole flow (PRD §7): one to index/reindex a codebase,
one to ask a question, optionally scoped to specific repos.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer

from codebase_rag.chunking import chunk_repo
from codebase_rag.config import load_config
from codebase_rag.embeddings import DEFAULT_MODEL, EmbeddingClient, OllamaEmbeddingClient
from codebase_rag.generation import ClaudeGenerator, Generator, RetrievedChunk
from codebase_rag.store import DEFAULT_DB_PATH, Store

TOP_K = 8
EMBED_BATCH_SIZE = 20

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

    # Embedded in batches, with a progress bar (FR-7) — the slow part is the
    # network round-trip to Ollama, so this is also where a large codebase
    # actually needs "roughly how far along it is".
    client: EmbeddingClient = OllamaEmbeddingClient()
    embeddings: list[list[float]] = []
    try:
        with typer.progressbar(range(0, len(chunks), EMBED_BATCH_SIZE), label="Embedding") as batches:
            for start in batches:
                batch = chunks[start : start + EMBED_BATCH_SIZE]
                embeddings.extend(client.embed([c.content for c in batch]))
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
    show: Optional[list[int]] = typer.Option(
        None, "--show", help="Print the full snippet behind citation number(s) after the answer (FR-4)."
    ),
) -> None:
    """Ask a question, grounded in retrieved source with citations (FR-2, FR-5)."""
    config = load_config()
    scope = repos or config.repo_names()
    if not scope:
        typer.echo("No repos configured yet - run 'codebase-rag index <repo>' first.")
        raise typer.Exit(code=1)

    if not DEFAULT_DB_PATH.exists():
        typer.echo("Nothing indexed yet - run 'codebase-rag index <repo>' first.")
        raise typer.Exit(code=1)

    started_at = time.monotonic()
    embed_client: EmbeddingClient = OllamaEmbeddingClient()
    try:
        [query_vector] = embed_client.embed([question])
    except Exception as exc:
        typer.echo(f"Embedding failed: {exc}")
        raise typer.Exit(code=1) from exc

    with Store(DEFAULT_DB_PATH) as store:
        known = set(store.indexed_repos())
        unindexed = [r for r in scope if r not in known]
        if unindexed:
            typer.echo(f"Not indexed yet: {unindexed}. Run 'codebase-rag index <repo>' for each first.")
            raise typer.Exit(code=1)
        rows = store.search(query_vector, repos=scope, top_k=TOP_K)

    if not rows:
        typer.echo("No indexed content matched - nothing to answer from.")
        raise typer.Exit(code=1)

    chunks = [
        RetrievedChunk(similarity=sim, repo=repo, file_path=path, start_line=start, end_line=end, content=content)
        for sim, repo, path, start, end, content in rows
    ]

    generator: Generator = ClaudeGenerator()
    try:
        answer = generator.generate(question, chunks)
    except Exception as exc:
        typer.echo(f"Generation failed: {exc}")
        raise typer.Exit(code=1) from exc

    latency_ms = round((time.monotonic() - started_at) * 1000)
    with Store(DEFAULT_DB_PATH) as store:
        store.log_query(question, scope, num_results=len(chunks), latency_ms=latency_ms)

    typer.echo(answer)
    typer.echo("\nSources:")
    for i, c in enumerate(chunks, start=1):
        typer.echo(f"  [{i}] {c.citation}")

    for n in show or []:
        if not 1 <= n <= len(chunks):
            typer.echo(f"\n--show {n}: no such citation (there are {len(chunks)}).")
            continue
        c = chunks[n - 1]
        typer.echo(f"\n--- [{n}] {c.citation} ---\n{c.content}")


@app.command()
def stats() -> None:
    """Queries/week off the query log (§5, §9) — a count, not a dashboard."""
    if not DEFAULT_DB_PATH.exists():
        typer.echo("Nothing indexed yet - no queries logged.")
        raise typer.Exit(code=1)

    since = datetime.now(timezone.utc) - timedelta(days=7)
    with Store(DEFAULT_DB_PATH) as store:
        count = store.queries_since(since)
    typer.echo(f"Queries in the last 7 days: {count}")


if __name__ == "__main__":
    app()
