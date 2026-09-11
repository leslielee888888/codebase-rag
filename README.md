# codebase-rag

Ask a question in plain English, get an answer grounded in your actual
source — across every codebase you've indexed, not just the one open in
front of you.

See the [PRD](https://github.com/leslielee888888/ai-docs/blob/main/docs/prd/codebase-rag-assistant.md)
for the full spec, and the [explainer](https://claude.ai/code/artifact/dcf9164b-9532-4eef-917a-a4f909633c27)
for a one-page summary.

## Usage

```sh
pip install .                        # installs the codebase-rag console script
cp config.example.yaml config.yaml   # fill in your real repo paths
ollama pull qwen3-embedding:0.6b     # once, before the first index
codebase-rag index <repo-name>
codebase-rag query "how does X work?" --repo <repo-name>
codebase-rag query "how does X work?" --show 1   # see the exact snippet behind citation [1]
codebase-rag chat                                # multi-turn conversation
codebase-rag stats                                # queries in the last 7 days
```

Needs an Ollama server running `qwen3-embedding:0.6b` (`OLLAMA_HOST`, default
`http://localhost:11434`) and a Claude Code login (`CLAUDE_CODE_OAUTH_TOKEN` —
generation goes through the Claude Agent SDK, not the raw Messages API; see
`generation.py`'s module docstring for why).

## NAS deployment

```sh
cp .env.example .env                 # fill in IMAGE_TAG and CLAUDE_CODE_OAUTH_TOKEN
cp config.example.yaml config.yaml   # fill in real repo paths — see that file for the /repos/<name> convention
docker compose up -d ollama
docker compose exec ollama ollama pull qwen3-embedding:0.6b   # first bring-up only
docker compose run --rm app index <repo-name>
docker compose run --rm app query "how does X work?" --repo <repo-name>
docker compose run --rm app chat
```

The Dockerfile's `ENTRYPOINT` is already `codebase-rag` — don't repeat it in
these commands (`docker compose run --rm app codebase-rag index ...` fails
with "No such command 'codebase-rag'").

`app` has no `restart:` policy on purpose — it's a CLI, invoked per command
with `docker compose run --rm`, not a long-running server (§7). Only `ollama`
stays up.

If GHCR is unreachable, see `docker-compose.build.yml` for a local-build
fallback (`docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`).

## Development

```sh
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
```
