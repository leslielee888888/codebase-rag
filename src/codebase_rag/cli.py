"""CLI entrypoint: `codebase-rag index`, `query`, `chat`, and `stats`.

`index`/`query` cover the core flow (PRD §7): one to index/reindex a
codebase, one to ask a question, optionally scoped to specific repos.
`chat` (FR-6) is the same retrieval/generation path with conversation
history carried across turns. `stats` reads the §5 queries/week metric off
the query log.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer

from codebase_rag import answering
from codebase_rag.chunking import chunk_repo
from codebase_rag.config import Config, ConfigError, load_config
from codebase_rag.embeddings import DEFAULT_MODEL, EmbeddingClient, OllamaEmbeddingClient
from codebase_rag.generation import ClaudeGenerator, Generator, RetrievedChunk, Turn
from codebase_rag.store import DEFAULT_DB_PATH, Store

EMBED_BATCH_SIZE = 20
# Caps how many prior turns go into the generation prompt (FR-6) — see
# answering.MAX_CHAT_HISTORY_TURNS, which _answer() actually enforces.
MAX_CHAT_HISTORY_TURNS = answering.MAX_CHAT_HISTORY_TURNS

app = typer.Typer(
    name="codebase-rag",
    help="Ask grounded, cited questions across every codebase you've indexed.",
    no_args_is_help=True,
)


def _load_config() -> Config:
    """`load_config()`, with a malformed config.yaml turned into a clean CLI
    error instead of a raw traceback."""
    try:
        return load_config()
    except ConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


@app.command()
def index(
    repo: str = typer.Argument(..., help="Name of the repo to index, as listed in config.yaml."),
) -> None:
    """Index (or reindex) one configured codebase (FR-1, FR-3)."""
    config = _load_config()
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


def _resolve_scope(repos: Optional[list[str]]) -> list[str]:
    config = _load_config()
    try:
        return answering.resolve_scope(repos, config.repo_names())
    except answering.NothingIndexedError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _answer(question: str, scope: list[str], history: Optional[list[Turn]] = None) -> tuple[str, list[RetrievedChunk]]:
    """Shared retrieve-then-generate path for `query` and `chat` (FR-2, FR-5, FR-6) —
    delegates the pipeline itself to `answering.answer_question` (reused by the
    v2 dashboard's API, §10 Q1), translating its typed errors into the CLI's
    echo-and-exit UX."""
    embed_client: EmbeddingClient = OllamaEmbeddingClient()
    generator: Generator = ClaudeGenerator()
    try:
        result = answering.answer_question(question, scope, history, embed_client, generator)
    except answering.EmbeddingFailedError as exc:
        typer.echo(f"Embedding failed: {exc}")
        raise typer.Exit(code=1) from exc
    except answering.UnindexedRepoError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    except answering.GenerationFailedError as exc:
        typer.echo(f"Generation failed: {exc}")
        raise typer.Exit(code=1) from exc
    except answering.AnsweringError as exc:
        # NothingIndexedError / NoMatchError — both are plain, complete
        # messages on their own (see answering.py).
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    return result.answer, result.chunks


def _print_answer(answer: str, chunks: list[RetrievedChunk], show: Optional[list[int]] = None) -> None:
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
    scope = _resolve_scope(repos)
    answer, chunks = _answer(question, scope)
    _print_answer(answer, chunks, show)


@app.command()
def chat(
    repos: Optional[list[str]] = typer.Option(
        None, "--repo", help="Repo(s) to scope the conversation to (repeatable). Default: all indexed repos."
    ),
) -> None:
    """Interactive multi-turn conversation (FR-6) — a follow-up reuses the prior turn as context."""
    scope = _resolve_scope(repos)
    typer.echo(f"Chatting over {scope}. Blank line or Ctrl+D to exit.\n")

    history: list[Turn] = []
    while True:
        try:
            # default="" makes a bare Enter return immediately as "" instead
            # of typer.prompt's normal behavior of re-asking on blank input —
            # without it, "blank line to exit" silently never exits.
            question = typer.prompt("Ask", prompt_suffix="> ", default="", show_default=False)
        except (typer.Abort, EOFError, KeyboardInterrupt):
            break
        if not question.strip():
            break

        answer, chunks = _answer(question, scope, history=history or None)
        _print_answer(answer, chunks)
        typer.echo("")
        history.append((question, answer))


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
