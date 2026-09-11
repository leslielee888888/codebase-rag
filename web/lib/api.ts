import { apiBase } from "./config";
import type { JobOut, QueryResponse, RepoInfo, Turn } from "./types";

/**
 * Thrown for any non-2xx API response. `status` lets callers distinguish
 * the backend's own error shapes (409 nothing indexed / already
 * reindexing, 404 no match, 502 embedding/generation failure, 422
 * validation) from a plain network failure; `message` is always a string
 * safe to show directly in the UI (the API's `detail` field, or a fallback).
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as { detail: unknown }).detail === "string" &&
      (body as { detail: string }).detail.length > 0
    ) {
      return (body as { detail: string }).detail;
    }
  } catch {
    // Response body wasn't JSON (or was empty) — fall through to the
    // generic message below.
  }
  return `Request failed (${response.status}).`;
}

/** Wraps `fetch` so every caller gets the same JSON-parse-or-throw shape. */
async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    throw new ApiError(0, "Couldn't reach the codebase-rag API. Is it running?");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  return (await response.json()) as T;
}

/** `GET /repos` (FR-4/T3) — every configured repo, indexed or not. */
export async function fetchRepos(signal?: AbortSignal): Promise<RepoInfo[]> {
  const data = await requestJson<{ repos: RepoInfo[] }>(`${apiBase()}/repos`, { signal });
  return data.repos;
}

/**
 * `POST /repos/{repo}/reindex` (FR-5a/T4) — enqueues a reindex as a
 * background job and returns immediately with its initial status. Throws an
 * `ApiError` with `status: 409` if `repo` is already reindexing (FR-5b), or
 * `400`/`404` if `repo` isn't configured or its path is missing.
 */
export async function triggerReindex(repo: string, signal?: AbortSignal): Promise<JobOut> {
  return requestJson<JobOut>(`${apiBase()}/repos/${encodeURIComponent(repo)}/reindex`, {
    method: "POST",
    signal,
  });
}

/**
 * `GET /repos/{repo}/reindex` (FR-5a/T4) — the latest reindex job for
 * `repo`. Poll this while `status` is `"running"`; it settles into `"done"`,
 * `"failed"`, or `"cancelled"`. Throws a `404` `ApiError` if no job has ever
 * run for `repo`.
 */
export async function fetchReindexStatus(repo: string, signal?: AbortSignal): Promise<JobOut> {
  return requestJson<JobOut>(`${apiBase()}/repos/${encodeURIComponent(repo)}/reindex`, {
    signal,
  });
}

/**
 * `DELETE /repos/{repo}/reindex` (FR-5c/T4) — requests cancellation of
 * `repo`'s running job; it stops at its next checkpoint rather than
 * instantly, so keep polling `fetchReindexStatus` until `status` is actually
 * `"cancelled"`. Throws an `ApiError` with `status: 409` if `repo` isn't
 * currently reindexing — not a fatal error, just stale UI state.
 */
export async function cancelReindex(repo: string, signal?: AbortSignal): Promise<JobOut> {
  return requestJson<JobOut>(`${apiBase()}/repos/${encodeURIComponent(repo)}/reindex`, {
    method: "DELETE",
    signal,
  });
}

export interface AskQuestionInput {
  question: string;
  /** Omit (or empty) to scope to every configured repo (FR-2). */
  repos?: string[];
  /** Prior (question, answer) turns in this session (FR-6). */
  history?: Turn[];
}

/** `POST /query` (FR-1, FR-2, FR-6). */
export async function askQuestion(
  input: AskQuestionInput,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  return requestJson<QueryResponse>(`${apiBase()}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: input.question,
      repos: input.repos && input.repos.length > 0 ? input.repos : undefined,
      history: input.history && input.history.length > 0 ? input.history : undefined,
    }),
    signal,
  });
}

export interface CitationLookup {
  repo: string;
  file_path: string;
  start_line: number;
  end_line: number;
}

/** `GET /citation` (FR-3/T2) — the exact snippet behind one citation. */
export async function fetchCitationSnippet(
  lookup: CitationLookup,
  signal?: AbortSignal,
): Promise<string> {
  const params = new URLSearchParams({
    repo: lookup.repo,
    file_path: lookup.file_path,
    start_line: String(lookup.start_line),
    end_line: String(lookup.end_line),
  });
  const data = await requestJson<{ content: string }>(
    `${apiBase()}/citation?${params.toString()}`,
    { signal },
  );
  return data.content;
}
