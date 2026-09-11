import { AskPage } from "@/components/ask/ask-page";
import { ApiError, fetchRepos } from "@/lib/api";

// Always fetch a fresh repo list — an indexed/last-indexed status that's
// even a page-load stale defeats the point of the empty/scope states.
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
  return <AskPage initialRepos={repos} initialReposError={error} />;
}
