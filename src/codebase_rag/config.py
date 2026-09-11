"""Repo-list config: which codebases this tool knows about.

Format decided in T1 (§10 Q2 of the PRD — a general tool over a configurable
list of repos, not one fixed codebase). Mirrors the project's existing
`.env`/`.env.example` convention: `config.yaml` is git-ignored and holds
Leslie's real repo paths; `config.example.yaml` is committed and shows the
shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True)
class RepoEntry:
    """One codebase this tool can index and query."""

    name: str
    path: str


@dataclass(frozen=True)
class Config:
    repos: list[RepoEntry]

    def repo_names(self) -> list[str]:
        return [r.name for r in self.repos]

    def find(self, name: str) -> RepoEntry | None:
        return next((r for r in self.repos if r.name == name), None)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load the repo list from `path`. Returns an empty Config if it doesn't exist yet."""
    if not path.exists():
        return Config(repos=[])

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("repos") or []
    repos = [RepoEntry(name=e["name"], path=e["path"]) for e in entries]
    return Config(repos=repos)
