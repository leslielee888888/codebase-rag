/** Mirrors the API's `CitationOut` (src/codebase_rag/api.py). */
export interface Citation {
  index: number;
  repo: string;
  file_path: string;
  start_line: number;
  end_line: number;
  citation: string;
}

/** Mirrors the API's `QueryResponse`. */
export interface QueryResponse {
  answer: string;
  citations: Citation[];
  latency_ms: number;
}

/** Mirrors the API's `RepoOut`. */
export interface RepoInfo {
  name: string;
  path: string;
  indexed: boolean;
  last_indexed_at: string | null;
}

/** A prior (question, answer) turn, same shape as the backend's `Turn`. */
export type Turn = [question: string, answer: string];

/** Mirrors the API's `JobRow.status` (src/codebase_rag/store.py). */
export type ReindexJobStatus = "running" | "done" | "failed" | "cancelled";

/**
 * Mirrors the API's `JobOut` (FR-5, T4/T8) — a reindex job's live or final
 * state. `total_chunks` is `null` until the job has scanned the repo and
 * knows how much work there is; `embedded_chunks` climbs in the meantime,
 * so real (if not yet percentage-based) progress is always available.
 */
export interface JobOut {
  job_id: number;
  repo: string;
  status: ReindexJobStatus;
  total_chunks: number | null;
  embedded_chunks: number;
  cancel_requested: boolean;
  error: string | null;
}
