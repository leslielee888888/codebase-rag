/**
 * Base URL of the codebase-rag dashboard API (T1-T6). Configurable via
 * `NEXT_PUBLIC_API_URL` so the same build can point at a different host once
 * deployed (T11) — defaults to the local `uvicorn`/`codebase-rag-api` port
 * for local dev.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

/**
 * Same-origin path a browser can call without hitting CORS — Next.js
 * rewrites it to `API_BASE_URL` server-to-server (see next.config.ts). The
 * API doesn't set CORS headers (not this task's surface to change), so
 * client components must go through this rather than `API_BASE_URL`
 * directly; a Server Component fetch (no browser involved) uses
 * `API_BASE_URL` directly instead.
 */
const CLIENT_PROXY_BASE = "/api/proxy";

/** The right base for the environment this code is running in. */
export function apiBase(): string {
  return typeof window === "undefined" ? API_BASE_URL : CLIENT_PROXY_BASE;
}
