"""Unit tests for chunking.py — no network, no I/O beyond the tmp_path fixture."""

from pathlib import Path

from codebase_rag.chunking import MAX_FILE_BYTES, chunk_file, chunk_repo, iter_source_files


def test_small_file_is_a_single_chunk(tmp_path: Path):
    f = tmp_path / "small.py"
    f.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")

    chunks = chunk_file("demo", tmp_path, f)

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 10
    assert chunks[0].file_path == "small.py"
    assert chunks[0].repo == "demo"


def test_large_file_splits_into_overlapping_windows(tmp_path: Path):
    f = tmp_path / "big.py"
    f.write_text("\n".join(f"line {i}" for i in range(250)), encoding="utf-8")

    chunks = chunk_file("demo", tmp_path, f)

    assert len(chunks) > 1
    # every line is covered by at least one chunk
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 250
    # consecutive chunks overlap
    assert chunks[1].start_line <= chunks[0].end_line


def test_binary_like_file_is_skipped(tmp_path: Path):
    f = tmp_path / "photo.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

    chunks = chunk_file("demo", tmp_path, f)

    assert chunks == []


def test_ignored_directories_are_not_walked(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "index.js").write_text("noise", encoding="utf-8")

    found = {p.name for p in iter_source_files(tmp_path)}

    assert found == {"app.py"}


def test_chunk_repo_covers_every_indexable_file(tmp_path: Path):
    (tmp_path / "a.py").write_text("a = 1", encoding="utf-8")
    (tmp_path / "b.py").write_text("b = 2", encoding="utf-8")

    chunks = chunk_repo("demo", tmp_path)

    assert {c.file_path for c in chunks} == {"a.py", "b.py"}


def test_ignored_suffix_is_skipped_by_iter_source_files(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    found = {p.name for p in iter_source_files(tmp_path)}

    assert found == {"app.py"}


def test_oversized_file_is_skipped_by_iter_source_files(tmp_path: Path):
    (tmp_path / "normal.py").write_text("x = 1", encoding="utf-8")
    huge = tmp_path / "generated.py"
    huge.write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    found = {p.name for p in iter_source_files(tmp_path)}

    assert found == {"normal.py"}


def test_empty_file_produces_no_chunks(tmp_path: Path):
    f = tmp_path / "empty.py"
    f.write_text("", encoding="utf-8")

    assert chunk_file("demo", tmp_path, f) == []


def test_sensitive_files_are_never_indexed(tmp_path: Path):
    """FR-1, hardened after PR #13's review: credentials never get embedded,
    stored, or sent to Claude, regardless of what a real repo happens to have
    checked in."""
    (tmp_path / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=abc123", encoding="utf-8")
    (tmp_path / ".env.production").write_text("SECRET=xyz789", encoding="utf-8")
    (tmp_path / "server.pem").write_text("-----BEGIN CERTIFICATE-----", encoding="utf-8")
    (tmp_path / "private.key").write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")
    (tmp_path / "id_rsa").write_text("-----BEGIN OPENSSH PRIVATE KEY-----", encoding="utf-8")
    (tmp_path / "aws_credentials").write_text("aws_access_key_id=AKIA...", encoding="utf-8")
    (tmp_path / ".netrc").write_text("machine example.com login x password y", encoding="utf-8")

    found = {p.name for p in iter_source_files(tmp_path)}

    assert found == {"app.py"}


def test_ssh_and_aws_directories_are_never_walked(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "id_ed25519").write_text("-----BEGIN OPENSSH PRIVATE KEY-----", encoding="utf-8")
    (tmp_path / ".aws").mkdir()
    (tmp_path / ".aws" / "credentials").write_text("[default]\naws_access_key_id=AKIA...", encoding="utf-8")

    found = {p.name for p in iter_source_files(tmp_path)}

    assert found == {"app.py"}
