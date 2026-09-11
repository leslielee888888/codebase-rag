interface ReposLoadErrorProps {
  message: string;
  onRetry: () => void;
  retrying: boolean;
}

/** The `GET /repos` call itself failed — can't tell empty vs. non-empty. */
export function ReposLoadError({ message, onRetry, retrying }: ReposLoadErrorProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div role="alert" className="max-w-sm text-center">
        <p className="font-mono text-sm text-error">Couldn&apos;t load your repos</p>
        <p className="mt-2 text-sm text-muted">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-4 rounded-md border border-line-strong px-4 py-2 font-mono text-sm text-ink transition-colors hover:bg-surface disabled:opacity-60"
        >
          {retrying ? "Retrying…" : "Retry"}
        </button>
      </div>
    </div>
  );
}
