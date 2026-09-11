"""Unit tests for config.py — direct, not just as a side effect of CLI tests
(PR #13's review)."""

from pathlib import Path

import pytest

from codebase_rag.config import Config, ConfigError, RepoEntry, load_config


def test_load_config_on_a_nonexistent_path_returns_empty_config(tmp_path: Path):
    assert load_config(tmp_path / "does-not-exist.yaml") == Config(repos=[])


def test_load_config_on_an_empty_file_returns_empty_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")

    assert load_config(path) == Config(repos=[])


def test_load_config_on_a_yaml_null_document_returns_empty_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("# just a comment, no content\n", encoding="utf-8")

    assert load_config(path) == Config(repos=[])


def test_load_config_with_no_repos_key_returns_empty_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("some_other_key: 1\n", encoding="utf-8")

    assert load_config(path) == Config(repos=[])


def test_load_config_with_an_empty_repos_list_returns_empty_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("repos: []\n", encoding="utf-8")

    assert load_config(path) == Config(repos=[])


def test_load_config_parses_repo_entries(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "repos:\n  - name: demo\n    path: /repos/demo\n  - name: other\n    path: /repos/other\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.repos == [
        RepoEntry(name="demo", path="/repos/demo"),
        RepoEntry(name="other", path="/repos/other"),
    ]


def test_load_config_rejects_a_non_mapping_top_level(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="expected a mapping"):
        load_config(path)


def test_load_config_rejects_repos_that_isnt_a_list(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("repos: not-a-list\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="'repos' must be a list"):
        load_config(path)


def test_load_config_rejects_a_non_mapping_entry(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("repos:\n  - just-a-string\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"repos\[0\] must be a mapping"):
        load_config(path)


def test_load_config_rejects_an_entry_missing_name(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("repos:\n  - path: /repos/demo\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"repos\[0\] is missing name"):
        load_config(path)


def test_load_config_rejects_an_entry_missing_path(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("repos:\n  - name: demo\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"repos\[0\] is missing path"):
        load_config(path)


def test_config_find_returns_the_matching_entry():
    config = Config(repos=[RepoEntry(name="a", path="/a"), RepoEntry(name="b", path="/b")])

    assert config.find("b") == RepoEntry(name="b", path="/b")


def test_config_find_returns_none_when_absent():
    config = Config(repos=[RepoEntry(name="a", path="/a")])

    assert config.find("missing") is None


def test_config_repo_names_preserves_order():
    config = Config(
        repos=[RepoEntry(name="z", path="/z"), RepoEntry(name="a", path="/a")],
    )

    assert config.repo_names() == ["z", "a"]
