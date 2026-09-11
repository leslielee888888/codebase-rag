# codebase-rag

Ask a question in plain English, get an answer grounded in your actual
source — across every codebase you've indexed, not just the one open in
front of you.

See the [PRD](https://github.com/leslielee888888/ai-docs/blob/main/docs/prd/codebase-rag-assistant.md)
for the full spec, and the [explainer](https://claude.ai/code/artifact/dcf9164b-9532-4eef-917a-a4f909633c27)
for a one-page summary.

## Usage (once indexing/query are implemented — T2/T3)

```sh
cp config.example.yaml config.yaml   # fill in your real repo paths
codebase-rag index <repo-name>
codebase-rag query "how does X work?" --repo <repo-name>
```

## Development

```sh
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
```
