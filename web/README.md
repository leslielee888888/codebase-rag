# codebase-rag dashboard

The web frontend for `codebase-rag` — the
[v2 "Codebase RAG Dashboard" PRD](https://github.com/leslielee888888/ai-docs/blob/main/docs/prd/codebase-rag-dashboard.md),
tracked as [`leslielee888888/codebase-rag#25`](https://github.com/leslielee888888/codebase-rag/issues/25).
Next.js (App Router) + TypeScript + Tailwind CSS, talking to the FastAPI
backend in `src/codebase_rag/api.py`.

Three pages:

- **Ask** (`/`) — ask a question, see a grounded answer with clickable
  citations, scope it to one or more repos, carry context across a
  follow-up.
- **Repos** (`/repos`) — every configured repo's indexed state and
  last-indexed time; trigger/cancel a reindex with real progress; add or
  remove a repo entry (removal asks for confirmation first).
- **History** (`/history`) — queries this week (split dashboard vs. CLI),
  and recent questions you can click to reveal their real stored answer.

Deployed alongside the API on the NAS as its own Docker image — see the
repo root `README.md`'s "NAS deployment" section and `Dockerfile` here.

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
