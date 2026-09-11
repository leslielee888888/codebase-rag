import type { Metadata } from "next";

export const metadata: Metadata = { title: "Repos — codebase-rag" };

/** Placeholder for T8 (repos panel — status, reindex, progress). */
export default function ReposPage() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <p className="max-w-sm text-center font-mono text-sm text-muted">
        The repos panel is coming in a later build — for now, use the Ask
        page to query your indexed repos.
      </p>
    </div>
  );
}
