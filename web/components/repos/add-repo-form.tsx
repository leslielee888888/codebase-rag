"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { addRepo, ApiError } from "@/lib/api";

interface AddRepoFormProps {
  /** Called once `POST /repos` succeeds, so the caller can refetch `GET
   * /repos` and show the new entry (FR-8a). */
  onAdded: () => void;
}

/** Add a repo entry already reachable on the NAS filesystem (FR-8a) — a UI
 * equivalent of hand-editing `config.yaml`, not a file-upload feature. */
export function AddRepoForm({ onAdded }: AddRepoFormProps) {
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const pathId = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    const trimmedPath = path.trim();
    if (!trimmedName || !trimmedPath) {
      setError("Name and path are both required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await addRepo({ name: trimmedName, path: trimmedPath });
      setName("");
      setPath("");
      onAdded();
    } catch (err) {
      // 409 (duplicate name) and 422 (missing fields) are the mistakes
      // worth calling out clearly; the API's `detail` message already does
      // that, so just surface it as-is.
      setError(err instanceof ApiError ? err.message : "Couldn't add this repo.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 sm:flex-row sm:items-end"
    >
      <div className="flex-1">
        <label htmlFor={nameId} className="block font-mono text-xs uppercase tracking-wide text-muted">
          Name
        </label>
        <input
          id={nameId}
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="my-repo"
          disabled={submitting}
          className="mt-1 w-full rounded-md border border-line-strong bg-canvas px-3 py-1.5 font-mono text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none disabled:opacity-60"
        />
      </div>
      <div className="flex-1">
        <label htmlFor={pathId} className="block font-mono text-xs uppercase tracking-wide text-muted">
          Path
        </label>
        <input
          id={pathId}
          type="text"
          value={path}
          onChange={(event) => setPath(event.target.value)}
          placeholder="/repos/my-repo"
          disabled={submitting}
          className="mt-1 w-full rounded-md border border-line-strong bg-canvas px-3 py-1.5 font-mono text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none disabled:opacity-60"
        />
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="rounded-md border border-line-strong px-4 py-1.5 font-mono text-sm text-ink transition-colors hover:bg-surface disabled:opacity-60"
      >
        {submitting ? "Adding…" : "Add repo"}
      </button>
      {error && (
        <p role="alert" className="w-full font-mono text-xs text-error">
          {error}
        </p>
      )}
    </form>
  );
}
