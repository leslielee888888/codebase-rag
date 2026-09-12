"use client";

import { useState } from "react";
import { ApiError, removeRepo } from "@/lib/api";

type RemovePhase = "idle" | "confirming" | "removing" | "error";

interface RemoveRepoControlProps {
  repo: string;
  /** Called once `DELETE /repos/{repo}` succeeds, so the caller can refetch
   * `GET /repos` and drop the entry from the list (FR-8b). */
  onRemoved: () => void;
}

/** Remove a repo entry (FR-8b) — gated behind an explicit confirm step
 * (§10 Q13): a misclick here costs real re-indexing time to undo, so it
 * can't be a single click. */
export function RemoveRepoControl({ repo, onRemoved }: RemoveRepoControlProps) {
  const [phase, setPhase] = useState<RemovePhase>("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function handleConfirm() {
    setPhase("removing");
    try {
      await removeRepo(repo);
      // Don't reset local state here — once the parent refetches `/repos`
      // and drops this entry, this row (and this control) unmounts.
      onRemoved();
    } catch (error) {
      setPhase("error");
      setMessage(error instanceof ApiError ? error.message : "Couldn't remove this repo.");
    }
  }

  if (phase === "confirming") {
    return (
      <div className="flex flex-col gap-1.5 rounded-md border border-error/40 bg-error/10 p-2">
        <p className="font-mono text-xs text-ink">Remove &quot;{repo}&quot;?</p>
        <p className="text-xs text-muted">Re-indexing it later takes real time to redo.</p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleConfirm}
            className="rounded-md border border-error px-2.5 py-1 font-mono text-xs text-error transition-colors hover:bg-error/10"
          >
            Remove
          </button>
          <button
            type="button"
            onClick={() => setPhase("idle")}
            className="rounded-md border border-line-strong px-2.5 py-1 font-mono text-xs text-ink transition-colors hover:bg-surface"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (phase === "removing") {
    return <span className="font-mono text-xs text-muted">Removing…</span>;
  }

  return (
    <div className="flex flex-col items-start gap-1">
      {phase === "error" && message && (
        <p role="alert" className="font-mono text-xs text-error">
          {message}
        </p>
      )}
      <button
        type="button"
        onClick={() => setPhase("confirming")}
        className="font-mono text-xs text-muted transition-colors hover:text-error"
      >
        Remove
      </button>
    </div>
  );
}
