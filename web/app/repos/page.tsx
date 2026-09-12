import type { Metadata } from "next";
import { ReposPage } from "@/components/repos/repos-page";
import { ApiError, fetchRepos } from "@/lib/api";

export const metadata: Metadata = { title: "Repos — codebase-rag" };

// Always fetch a fresh repo list — matches the Ask page (T7): an
// indexed/last-indexed status that's even page-load stale defeats FR-4.
export const dynamic = "force-dynamic";

async function loadInitialRepos() {
  try {
    return { repos: await fetchRepos(), error: null };
  } catch (error) {
    const message = error instanceof ApiError ? error.message : "Something went wrong.";
    return { repos: null, error: message };
  }
}

export default async function Page() {
  const { repos, error } = await loadInitialRepos();
  return <ReposPage initialRepos={repos} initialReposError={error} />;
}
