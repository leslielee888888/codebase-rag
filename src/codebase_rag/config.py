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


class ConfigError(ValueError):
    """config.yaml is malformed — bad YAML syntax or a structure `load_config`
    doesn't recognize. Raised with a message naming the actual problem, so
    cli.py can show it plainly instead of a raw parser/KeyError/TypeError
    traceback."""


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
    """Load the repo list from `path`. Returns an empty Config if it doesn't
    exist, or exists but is empty. Raises `ConfigError` — never a raw
    KeyError/TypeError — for anything else malformed."""
    if not path.exists():
        return Config(repos=[])

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return Config(repos=[])

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML — {exc}") from exc
    if raw is None:
        return Config(repos=[])
    if not isinstance(raw, dict):
        raise ConfigError(
            f"{path}: expected a mapping with a 'repos:' list at the top level, "
            f"got {type(raw).__name__}."
        )

    entries = raw.get("repos")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ConfigError(f"{path}: 'repos' must be a list, got {type(entries).__name__}.")

    repos: list[RepoEntry] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigError(
                f"{path}: repos[{i}] must be a mapping with 'name' and 'path', "
                f"got {type(entry).__name__}."
            )
        missing = [key for key in ("name", "path") if key not in entry]
        if missing:
            raise ConfigError(
                f"{path}: repos[{i}] is missing {', '.join(missing)} "
                f"(got keys: {', '.join(sorted(entry.keys())) or 'none'})."
            )
        repos.append(RepoEntry(name=entry["name"], path=entry["path"]))
    return Config(repos=repos)
