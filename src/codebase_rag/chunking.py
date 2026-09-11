"""Walk a codebase and cut it into indexable chunks (FR-1).

Chunking is intentionally language-agnostic: fixed-size, overlapping line
windows per file, never spanning file boundaries. The corpus this tool
indexes is small (~15MB across all of Leslie's repos per the PRD's own
numbers) and spans several languages, so a per-language parser would be
more machinery than the problem needs — see the PRD's "simplest that
fits" standing preference.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MAX_LINES_PER_CHUNK = 100
OVERLAP_LINES = 20
MAX_FILE_BYTES = 1_000_000  # skip generated/minified/binary-ish files

# Directories no codebase-indexing tool should walk into.
IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

# Extensions that are essentially never useful source text for retrieval.
IGNORED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".7z",
    ".pyc", ".pyo", ".so", ".dll", ".exe",
    ".lock",
}


@dataclass(frozen=True)
class Chunk:
    """One indexable slice of a file: `repo`-relative `file_path`, its
    1-indexed inclusive line range, and the text itself."""

    repo: str
    file_path: str
    start_line: int
    end_line: int
    content: str


def _is_indexable(path: Path) -> bool:
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def iter_source_files(root: Path):
    """Yield every indexable file under `root`, skipping ignored directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if _is_indexable(path):
                yield path


def chunk_file(repo: str, root: Path, path: Path) -> list[Chunk]:
    """Cut one file into overlapping line-window chunks."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # not UTF-8 text (binary) or unreadable — skip it

    lines = text.splitlines()
    if not lines:
        return []

    rel_path = path.relative_to(root).as_posix()
    chunks: list[Chunk] = []
    start = 0
    stride = MAX_LINES_PER_CHUNK - OVERLAP_LINES
    while start < len(lines):
        end = min(start + MAX_LINES_PER_CHUNK, len(lines))
        window = "\n".join(lines[start:end])
        chunks.append(
            Chunk(
                repo=repo,
                file_path=rel_path,
                start_line=start + 1,
                end_line=end,
                content=window,
            )
        )
        if end == len(lines):
            break
        start += stride
    return chunks


def chunk_repo(repo: str, root: Path) -> list[Chunk]:
    """Chunk every indexable file under a repo's root."""
    chunks: list[Chunk] = []
    for path in iter_source_files(root):
        chunks.extend(chunk_file(repo, root, path))
    return chunks
