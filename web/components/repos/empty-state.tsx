import { AddRepoForm } from "./add-repo-form";

interface EmptyStateProps {
  /** Called once a repo is successfully added, so the caller can refetch
   * `GET /repos` and this empty state gives way to the repo table. */
  onAdded: () => void;
}

/** No repos configured at all — prompt to add one (FR-8) rather than a
 * blank query box with nothing to ask about. */
export function EmptyState({ onAdded }: EmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-md text-center">
        <p className="font-mono text-sm text-ink">No repos configured yet</p>
        <p className="mt-2 text-sm text-muted">
          Add a repo whose content is already reachable on the NAS to make it
          indexable.
        </p>
        <div className="mt-4 text-left">
          <AddRepoForm onAdded={onAdded} />
        </div>
      </div>
    </div>
  );
}
