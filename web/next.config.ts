import type { NextConfig } from "next";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

const nextConfig: NextConfig = {
  // A self-contained `.next/standalone` server (T11) - the Docker image
  // copies just that output plus `public`/`.next/static`, not the full
  // `node_modules`.
  output: "standalone",
  // Client components (the composer, citation clicks, reindex polling) call
  // the browser-relative `/api/proxy/*` path instead of the backend
  // directly; this rewrite forwards it server-to-server. That's what lets
  // the deployed `api` service (T11) stay off the LAN entirely — only this
  // `web` container's own published port needs to be reachable, and the
  // browser never needs to know `api`'s address. (api.py does have CORS
  // enabled too, as of T7's cleanup - this proxy just means it's never
  // exercised from a real browser.) Server Components (app/page.tsx) call
  // the API directly and don't need this at all.
  async rewrites() {
    return [{ source: "/api/proxy/:path*", destination: `${API_BASE_URL}/:path*` }];
  },
};

export default nextConfig;
