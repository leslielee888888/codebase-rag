"use client";

import { useState } from "react";
import { ApiError, fetchRepos } from "@/lib/api";
import type { RepoInfo } from "@/lib/types";
import { ReposLoadError } from "@/components/ask/repos-load-error";
import { TopBar } from "@/components/ask/top-bar";
import { EmptyState } from "./empty-state";
import { RepoTable } from "./repo-table";

interface ReposPageProps {
  /** Seeded from a server-side `GET /repos` call — `null` if that failed. */
  initialRepos: RepoInfo[] | null;
  initialReposError: string | null;
}

/** The Repos view (FR-4, FR-5) — status, and reindex trigger/progress/cancel. */
export function ReposPage({ initialRepos, initialReposError }: ReposPageProps) {
  const [repos, setRepos] = useState<RepoInfo[]>(initialRepos ?? []);
  const [reposError, setReposError] = useState<string | null>(initialReposError);
  const [reposRetrying, setReposRetrying] = useState(false);

  async function retryRepos() {
    setReposRetrying(true);
    try {
      const next = await fetchRepos();
      setRepos(next);
      setReposError(null);
    } catch (error) {
      setReposError(error instanceof ApiError ? error.message : "Something went wrong.");
    } finally {
      setReposRetrying(false);
    }
  }

  /** Called once a reindex job settles, so indexed/last-indexed reflect it.
   * Fails silently on top of whatever the table already shows — a row's own
   * job state still reflects the real outcome even if this refresh drops. */
  async function refreshRepos() {
    try {
      setRepos(await fetchRepos());
    } catch {
      // keep showing the last known list
    }
  }

  if (reposError !== null && repos.length === 0) {
    return <ReposLoadError message={reposError} onRetry={retryRepos} retrying={reposRetrying} />;
  }

  if (repos.length === 0) {
    return <EmptyState />;
  }

  return (
    <>
      <TopBar title="Repos" />
      <div className="flex-1 overflow-y-auto p-6">
        <RepoTable repos={repos} onReindexed={refreshRepos} />
      </div>
    </>
  );
}
