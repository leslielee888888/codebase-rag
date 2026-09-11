import type { NextConfig } from "next";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

const nextConfig: NextConfig = {
  // The FastAPI backend (src/codebase_rag/api.py) doesn't set CORS headers,
  // and isn't this frontend's to change (out of scope for T7 — it's
  // T1-T6's already-shipped, already-tested surface). Client components
  // (the composer, citation clicks) call the browser-relative
  // `/api/proxy/*` path instead of the backend directly; this rewrite
  // forwards it server-to-server, which isn't subject to the browser's
  // CORS check. Server Components (app/page.tsx) call the API directly and
  // don't need this at all.
  async rewrites() {
    return [{ source: "/api/proxy/:path*", destination: `${API_BASE_URL}/:path*` }];
  },
};

export default nextConfig;
