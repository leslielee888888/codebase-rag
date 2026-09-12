/** Nothing logged yet — no queries have run through either surface. */
export function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-md text-center">
        <p className="font-mono text-sm text-ink">No queries logged yet</p>
        <p className="mt-2 text-sm text-muted">
          Ask a question from the Ask page and it&apos;ll show up here, with its
          answer revisitable any time.
        </p>
      </div>
    </div>
  );
}
