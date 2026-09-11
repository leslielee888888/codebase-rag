# python:3.11-slim (Debian) plus Node.js — the Claude Agent SDK's Python
# client is a thin wrapper that spawns the real Claude Code CLI as a
# subprocess (see generation.py's module docstring for why this is
# unavoidable: raw Messages API calls are rejected on this Anthropic org).
# `@anthropic-ai/claude-code` ships that CLI as an npm package.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .

ENTRYPOINT ["codebase-rag"]
