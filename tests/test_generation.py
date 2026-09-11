"""Unit tests for generation.py — the Anthropic API call is never exercised
here; only prompt-building, which is pure and network-free."""

from codebase_rag.generation import RetrievedChunk, build_prompt


def test_build_prompt_numbers_and_cites_every_chunk():
    chunks = [
        RetrievedChunk(0.9, "demo", "a.py", 1, 10, "def foo(): ..."),
        RetrievedChunk(0.8, "demo", "b.py", 5, 8, "def bar(): ..."),
    ]

    prompt = build_prompt("how does foo work?", chunks)

    assert "[1] demo/a.py:1-10" in prompt
    assert "[2] demo/b.py:5-8" in prompt
    assert "def foo(): ..." in prompt
    assert "how does foo work?" in prompt


def test_citation_property_formats_file_and_line_range():
    chunk = RetrievedChunk(0.5, "demo", "src/app.py", 12, 34, "...")
    assert chunk.citation == "demo/src/app.py:12-34"


def test_build_prompt_includes_prior_turns_when_given_history():
    chunks = [RetrievedChunk(0.9, "demo", "a.py", 1, 5, "def foo(): ...")]

    prompt = build_prompt(
        "what about errors?",
        chunks,
        history=[("how does foo work?", "It calls bar().")],
    )

    assert "Previous turns in this conversation:" in prompt
    assert "Q: how does foo work?" in prompt
    assert "A: It calls bar()." in prompt
    assert "Question: what about errors?" in prompt


def test_build_prompt_omits_prior_turns_section_without_history():
    chunks = [RetrievedChunk(0.9, "demo", "a.py", 1, 5, "def foo(): ...")]

    prompt = build_prompt("how does foo work?", chunks)

    assert "Previous turns" not in prompt
