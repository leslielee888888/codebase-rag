import type { RepoInfo } from "@/lib/types";
import { RepoRow } from "./repo-row";

interface RepoTableProps {
  repos: RepoInfo[];
  onReindexed: () => void;
  /** Notifies the parent to refetch `GET /repos` once a repo is removed
   * (FR-8b). */
  onRemoved: () => void;
}

/** Every configured repo (FR-4) with its own reindex (FR-5) and
 * add/remove (FR-8) controls. */
export function RepoTable({ repos, onReindexed, onRemoved }: RepoTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[560px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line bg-surface">
            <th scope="col" className="px-3 py-2 font-mono text-xs font-medium uppercase tracking-wide text-muted">
              Repo
            </th>
            <th scope="col" className="px-3 py-2 font-mono text-xs font-medium uppercase tracking-wide text-muted">
              Status
            </th>
            <th scope="col" className="px-3 py-2 font-mono text-xs font-medium uppercase tracking-wide text-muted">
              Last indexed
            </th>
            <th scope="col" className="px-3 py-2 font-mono text-xs font-medium uppercase tracking-wide text-muted">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {repos.map((repo) => (
            <RepoRow key={repo.name} repo={repo} onReindexed={onReindexed} onRemoved={onRemoved} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
