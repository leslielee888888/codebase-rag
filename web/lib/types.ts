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
