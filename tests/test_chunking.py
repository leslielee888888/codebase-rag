"""Unit tests for chunking.py — no network, no I/O beyond the tmp_path fixture."""

from pathlib import Path

from codebase_rag.chunking import chunk_file, chunk_repo, iter_source_files


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
