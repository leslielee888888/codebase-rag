import type { Metadata } from "next";
import { HistoryPage } from "@/components/history/history-page";
import { ApiError, fetchHistory, fetchStats } from "@/lib/api";

export const metadata: Metadata = { title: "History — codebase-rag" };

// Always fetch fresh — matches Ask/Repos (T7/T8): a queries-this-week count
// or history list that's even page-load stale defeats FR-7.
export const dynamic = "force-dynamic";

async function loadInitialHistory() {
  try {
    const [stats, entries] = await Promise.all([fetchStats(), fetchHistory()]);
    return { stats, entries, error: null };
  } catch (error) {
    const message = error instanceof ApiError ? error.message : "Something went wrong.";
    return { stats: null, entries: null, error: message };
  }
}

export default async function Page() {
  const { stats, entries, error } = await loadInitialHistory();
  return <HistoryPage initialStats={stats} initialEntries={entries} initialError={error} />;
}
