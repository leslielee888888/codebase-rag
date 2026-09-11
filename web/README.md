# codebase-rag dashboard

The web frontend for `codebase-rag` (v2 "Codebase RAG Dashboard" PRD,
[`leslielee888888/codebase-rag#21`](https://github.com/leslielee888888/codebase-rag/issues/21)).
Next.js (App Router) + TypeScript + Tailwind CSS, talking to the FastAPI
backend in `src/codebase_rag/api.py`.

This slice (T7) is the Ask/chat page — ask a question, see a grounded
answer with clickable citations, scope it to one or more repos, and carry
context across a follow-up. Repos and History in the sidebar are
placeholders for T8/T10.

## Run locally

The API must be running first (from the repo root):

```sh
uvicorn codebase_rag.api:app --reload   # or: codebase-rag-api
```

Then, from `web/`:

```sh
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL — defaults to localhost:8000, edit if the API runs elsewhere
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Test

```sh
npm test          # Vitest + React Testing Library, single run
npm run test:watch
```

## Other checks

```sh
npx tsc --noEmit
npm run lint
npm run build
```
