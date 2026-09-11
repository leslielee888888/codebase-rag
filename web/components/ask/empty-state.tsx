/** No repos configured at all — prompts to add one instead of a live query box. */
export function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="max-w-sm text-center">
        <p className="font-mono text-sm text-ink">No repos configured yet</p>
        <p className="mt-2 text-sm text-muted">
          codebase-rag has nothing to search until a repo is added and
          indexed. Adding a repo from the dashboard is coming in a later
          build — for now, add one to <code className="font-mono text-xs text-faint">config.yaml</code>{" "}
          and index it with the CLI.
        </p>
      </div>
    </div>
  );
}
