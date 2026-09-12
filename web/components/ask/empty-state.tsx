import Link from "next/link";

/** No repos configured at all — prompts to add one instead of a live query box. */
export function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="max-w-sm text-center">
        <p className="font-mono text-sm text-ink">No repos configured yet</p>
        <p className="mt-2 text-sm text-muted">
          codebase-rag has nothing to search until a repo is added and
          indexed. Add one from the{" "}
          <Link href="/repos" className="text-accent underline underline-offset-2 hover:opacity-80">
            Repos
          </Link>{" "}
          page, then trigger a reindex.
        </p>
      </div>
    </div>
  );
}
