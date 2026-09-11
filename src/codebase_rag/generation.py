"""Generation: Claude Sonnet 5 answers a question grounded in retrieved chunks (FR-2).

Sonnet 5 over Opus 5 (§10 Q5) — grounded Q&A over retrieved source isn't
frontier-reasoning work, and this runs per query.

**Why this goes through the Claude Agent SDK, not the raw `anthropic` SDK:**
the sibling `aus-tax-lodge` project already hit this exact wall on this same
Anthropic org (T16) — a raw `messages.create()` call with the subscription
OAuth token gets rejected with a `429 rate_limit_error`
(`overageDisabledReason: "org_level_disabled"`), because raw API-style access
outside the actual Claude Code product isn't enabled for this account at the
org level. The fix there, which this mirrors: `claude_agent_sdk.query()`
spawns the real Claude Code CLI as a subprocess, which authenticates the same
`CLAUDE_CODE_OAUTH_TOKEN` successfully because it *is* Claude Code. The
subprocess picks the token up from the environment on its own — nothing here
passes a credential explicitly. This still needs a real authenticated call
against the deployed NAS container to confirm (T10), the same way T16 did.

`history` (FR-6) is the prior turns of a `chat` session: included in the
prompt so a follow-up like "what about the edge cases?" resolves against
what was just discussed, not just the bare question.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

Turn = tuple[str, str]  # (question, answer)

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You answer questions about a codebase using only the numbered source "
    "excerpts you're given. Ground every claim in a specific excerpt by "
    "referring to its number, like [2]. If the excerpts don't contain the "
    "answer, say so plainly instead of guessing."
)


@dataclass(frozen=True)
class RetrievedChunk:
    """One search result: `store.search()`'s row, named for readability."""

    similarity: float
    repo: str
    file_path: str
    start_line: int
    end_line: int
    content: str

    @property
    def citation(self) -> str:
        return f"{self.repo}/{self.file_path}:{self.start_line}-{self.end_line}"


class Generator(Protocol):
    def generate(self, question: str, chunks: list[RetrievedChunk], history: list[Turn] | None = None) -> str:
        """Return an answer grounded in `chunks`, optionally continuing `history` (FR-6)."""
        ...


def build_prompt(question: str, chunks: list[RetrievedChunk], history: list[Turn] | None = None) -> str:
    sources = "\n\n".join(
        f"[{i}] {c.citation}\n{c.content}" for i, c in enumerate(chunks, start=1)
    )
    prior = ""
    if history:
        turns = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in history)
        prior = f"Previous turns in this conversation:\n\n{turns}\n\n"
    return f"{prior}Sources:\n\n{sources}\n\nQuestion: {question}"


class ClaudeGenerator:
    """Generates via the Claude Agent SDK (Sonnet 5, subscription OAuth auth) —
    see the module docstring for why not the raw Messages API."""

    def __init__(self, model: str = MODEL):
        self._model = model

    def generate(self, question: str, chunks: list[RetrievedChunk], history: list[Turn] | None = None) -> str:
        return asyncio.run(self._generate_async(question, chunks, history))

    async def _generate_async(
        self, question: str, chunks: list[RetrievedChunk], history: list[Turn] | None
    ) -> str:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=SYSTEM_PROMPT,
            tools=[],  # answer from the prompt's own sources only — no file/bash access
            max_turns=1,  # single-shot Q&A, not an agentic session
        )

        text_parts: list[str] = []
        async for message in query(prompt=build_prompt(question, chunks, history), options=options):
            if isinstance(message, AssistantMessage):
                text_parts.extend(block.text for block in message.content if isinstance(block, TextBlock))
        return "".join(text_parts)
