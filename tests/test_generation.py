"""Unit tests for generation.py, including ClaudeGenerator itself — the real
claude_agent_sdk.query() is replaced with a fake async generator, so these
never spawn the actual Claude Code CLI subprocess or need real credentials."""

import asyncio

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

import codebase_rag.generation as generation_module
from codebase_rag.generation import ClaudeGenerator, RetrievedChunk, build_prompt


def _assistant_message(*texts: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=t) for t in texts], model="claude-sonnet-5")


def _one_chunk() -> list[RetrievedChunk]:
    return [RetrievedChunk(1.0, "demo", "a.py", 1, 1, "x = 1")]


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


def test_generate_concatenates_text_across_multiple_assistant_messages(monkeypatch):
    async def fake_query(*, prompt, options):
        yield _assistant_message("Part one. ")
        yield _assistant_message("Part two.")

    monkeypatch.setattr(generation_module, "query", fake_query)

    answer = ClaudeGenerator().generate("q?", _one_chunk())

    assert answer == "Part one. Part two."


def test_generate_filters_non_text_blocks_and_non_assistant_messages(monkeypatch):
    class NotAMessage:
        """Stands in for SystemMessage/ResultMessage/etc — anything that isn't AssistantMessage."""

    class NotATextBlock:
        text = "should never appear in the answer"

    async def fake_query(*, prompt, options):
        yield NotAMessage()
        yield AssistantMessage(content=[NotATextBlock(), TextBlock(text="real text")], model="claude-sonnet-5")

    monkeypatch.setattr(generation_module, "query", fake_query)

    answer = ClaudeGenerator().generate("q?", _one_chunk())

    assert answer == "real text"


def test_generate_raises_when_no_text_content_is_returned(monkeypatch):
    async def empty_query(*, prompt, options):
        return
        yield  # pragma: no cover — makes this a generator function with an empty stream

    monkeypatch.setattr(generation_module, "query", empty_query)

    with pytest.raises(RuntimeError, match="no text content"):
        ClaudeGenerator().generate("q?", _one_chunk())


def test_generate_passes_model_and_restricts_to_no_tools_single_turn(monkeypatch):
    captured = {}

    async def fake_query(*, prompt, options):
        captured["options"] = options
        yield _assistant_message("ok")

    monkeypatch.setattr(generation_module, "query", fake_query)

    ClaudeGenerator(model="claude-sonnet-5").generate("q?", _one_chunk())

    options = captured["options"]
    assert options.model == "claude-sonnet-5"
    assert options.tools == []
    assert options.max_turns == 1


def test_generate_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(generation_module, "GENERATION_TIMEOUT_SECONDS", 0.05)

    async def hanging_query(*, prompt, options):
        await asyncio.sleep(1)
        yield _assistant_message("too late")

    monkeypatch.setattr(generation_module, "query", hanging_query)

    with pytest.raises(asyncio.TimeoutError):
        ClaudeGenerator().generate("q?", _one_chunk())
