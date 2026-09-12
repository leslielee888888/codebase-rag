"use client";

import { useState } from "react";
import { TopBar } from "@/components/ask/top-bar";
import { ApiError, fetchHistory, fetchStats } from "@/lib/api";
import type { HistoryEntry, Stats } from "@/lib/types";
import { EmptyState } from "./empty-state";
import { HistoryList } from "./history-list";
import { LoadError } from "./load-error";
import { StatsPanel } from "./stats-panel";

interface HistoryPageProps {
  /** Seeded from server-side `GET /stats` + `GET /history` calls — both
   * `null` if either failed (they're fetched together; a partial failure
   * still lands here as the same load-error state as the Repos/Ask pages
   * use for their own single seed call). */
  initialStats: Stats | null;
  initialEntries: HistoryEntry[] | null;
  initialError: string | null;
}

/** The History/Stats view (FR-7) — queries/week and revisitable past answers. */
export function HistoryPage({ initialStats, initialEntries, initialError }: HistoryPageProps) {
  const [stats, setStats] = useState<Stats | null>(initialStats);
  const [entries, setEntries] = useState<HistoryEntry[]>(initialEntries ?? []);
  const [error, setError] = useState<string | null>(initialError);
  const [retrying, setRetrying] = useState(false);

  async function retry() {
    setRetrying(true);
    try {
      const [nextStats, nextEntries] = await Promise.all([fetchStats(), fetchHistory()]);
      setStats(nextStats);
      setEntries(nextEntries);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setRetrying(false);
    }
  }

  if (error !== null && stats === null) {
    return <LoadError message={error} onRetry={retry} retrying={retrying} />;
  }

  return (
    <>
      <TopBar title="History" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex flex-col gap-6">
          {stats && <StatsPanel stats={stats} />}
          {entries.length === 0 ? <EmptyState /> : <HistoryList entries={entries} />}
        </div>
      </div>
    </>
  );
}
