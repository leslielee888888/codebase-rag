import type { Metadata } from "next";

export const metadata: Metadata = { title: "History — codebase-rag" };

/** Placeholder for T10 (history/stats panel). */
export default function HistoryPage() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <p className="max-w-sm text-center font-mono text-sm text-muted">
        Query history and stats are coming in a later build — for now, use
        the Ask page to query your indexed repos.
      </p>
    </div>
  );
}
