"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, cancelReindex, fetchReindexStatus, triggerReindex } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { JobOut, RepoInfo } from "@/lib/types";
import { RemoveRepoControl } from "./remove-repo-control";

/** How often to re-poll a running (or cancelling) reindex job. */
const POLL_INTERVAL_MS = 2000;

type RowState =
  // Checking for a job this row doesn't know about yet — e.g. right after
  // mount, in case a reindex from a prior session (or another tab) is still
  // running; jobs are SQLite-backed (§10 Q10) so they outlive a reload.
  | { phase: "checking" }
  | { phase: "idle" }
  | { phase: "starting" }
  | { phase: "running"; job: JobOut }
  | { phase: "cancelling"; job: JobOut }
  | { phase: "settled"; job: JobOut }
  | { phase: "error"; message: string };

interface RepoRowProps {
  repo: RepoInfo;
  /** Notifies the parent to refetch `GET /repos` once a job finishes, so the
   * indexed/last-indexed columns reflect the new state. */
  onReindexed: () => void;
  /** Notifies the parent to refetch `GET /repos` once this repo is removed
   * (FR-8b), so it drops out of the list. */
  onRemoved: () => void;
  /** Poll cadence for a running/cancelling job. A test-only knob — the real
   * app always uses the `POLL_INTERVAL_MS` default. */
  pollIntervalMs?: number;
}

export function RepoRow({ repo, onReindexed, onRemoved, pollIntervalMs = POLL_INTERVAL_MS }: RepoRowProps) {
  const [state, setState] = useState<RowState>({ phase: "checking" });
  const mountedRef = useRef(true);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const job = await fetchReindexStatus(repo.name);
        if (cancelled || !mountedRef.current) return;
        if (job.status === "running") {
          setState(job.cancel_requested ? { phase: "cancelling", job } : { phase: "running", job });
          schedulePoll();
        } else {
          // A terminal job from a previous session — the repos table
          // already reflects its outcome via `last_indexed_at`; don't show
          // a stale done/failed/cancelled banner for something that didn't
          // just happen in this session.
          setState({ phase: "idle" });
        }
      } catch {
        if (cancelled || !mountedRef.current) return;
        // No job has ever run for this repo (404) — plain idle, not an error.
        setState({ phase: "idle" });
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only check once on mount for this repo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo.name]);

  function schedulePoll() {
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    pollTimeoutRef.current = setTimeout(poll, pollIntervalMs);
  }

  async function poll() {
    try {
      const job = await fetchReindexStatus(repo.name);
      if (!mountedRef.current) return;
      if (job.status === "running") {
        setState(job.cancel_requested ? { phase: "cancelling", job } : { phase: "running", job });
        schedulePoll();
      } else {
        setState({ phase: "settled", job });
        onReindexed();
      }
    } catch (error) {
      if (!mountedRef.current) return;
      const message =
        error instanceof ApiError ? error.message : "Lost track of this reindex job.";
      setState({ phase: "error", message });
    }
  }

  async function handleTrigger() {
    setState({ phase: "starting" });
    try {
      const job = await triggerReindex(repo.name);
      if (!mountedRef.current) return;
      setState({ phase: "running", job });
      schedulePoll();
    } catch (error) {
      if (!mountedRef.current) return;
      const message =
        error instanceof ApiError ? error.message : "Couldn't start a reindex.";
      setState({ phase: "error", message });
    }
  }

  async function handleCancel() {
    if (state.phase !== "running") return;
    setState({ phase: "cancelling", job: state.job });
    try {
      const job = await cancelReindex(repo.name);
      if (!mountedRef.current) return;
      if (job.status === "running") {
        setState({ phase: "cancelling", job });
        schedulePoll();
      } else {
        setState({ phase: "settled", job });
        onReindexed();
      }
    } catch (error) {
      if (!mountedRef.current) return;
      // A 409 here just means it wasn't actually running any more (e.g. it
      // finished between polls) — surface the message, but don't treat it
      // as fatal: fall back to idle so the row is usable again.
      const message =
        error instanceof ApiError ? error.message : "Couldn't cancel this reindex.";
      setState({ phase: "error", message });
    }
  }

  const isBusy = state.phase === "starting" || state.phase === "running" || state.phase === "cancelling";

  return (
    <tr className="border-b border-line last:border-b-0">
      <td className="px-3 py-3 align-top">
        <p className="font-mono text-sm text-ink">{repo.name}</p>
        <p className="mt-0.5 font-mono text-xs text-faint">{repo.path}</p>
      </td>
      <td className="px-3 py-3 align-top">
        <StatusBadge repo={repo} isBusy={isBusy} />
      </td>
      <td className="px-3 py-3 align-top font-mono text-xs text-muted">
        {repo.indexed && repo.last_indexed_at ? formatRelativeTime(repo.last_indexed_at) : "—"}
      </td>
      <td className="px-3 py-3 align-top">
        <div className="flex flex-col items-start gap-2">
          <RowActions state={state} onTrigger={handleTrigger} onCancel={handleCancel} />
          <RemoveRepoControl repo={repo.name} onRemoved={onRemoved} />
        </div>
      </td>
    </tr>
  );
}

function StatusBadge({ repo, isBusy }: { repo: RepoInfo; isBusy: boolean }) {
  if (isBusy) {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs text-accent">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-accent" />
        Reindexing
      </span>
    );
  }
  if (repo.indexed) {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs text-success">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-success" />
        Indexed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs text-faint">
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-faint" />
      Not indexed
    </span>
  );
}

interface RowActionsProps {
  state: RowState;
  onTrigger: () => void;
  onCancel: () => void;
}

function RowActions({ state, onTrigger, onCancel }: RowActionsProps) {
  switch (state.phase) {
    case "checking":
      return <span className="font-mono text-xs text-faint">…</span>;

    case "idle":
      return <ReindexButton onClick={onTrigger} />;

    case "starting":
      return (
        <button
          type="button"
          disabled
          className="rounded-md border border-line-strong px-3 py-1.5 font-mono text-xs text-muted opacity-60"
        >
          Starting…
        </button>
      );

    case "running":
      return (
        <div className="flex flex-col gap-2">
          <ReindexProgress job={state.job} cancelling={false} />
          <button
            type="button"
            onClick={onCancel}
            className="self-start rounded-md border border-line-strong px-3 py-1.5 font-mono text-xs text-ink transition-colors hover:bg-surface"
          >
            Cancel
          </button>
        </div>
      );

    case "cancelling":
      return <ReindexProgress job={state.job} cancelling />;

    case "settled":
      return (
        <div className="flex flex-col gap-1">
          <SettledMessage job={state.job} />
          <ReindexButton onClick={onTrigger} />
        </div>
      );

    case "error":
      return (
        <div className="flex flex-col gap-1">
          <p role="alert" className="font-mono text-xs text-error">
            {state.message}
          </p>
          <ReindexButton onClick={onTrigger} />
        </div>
      );

    default:
      return null;
  }
}

function ReindexButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-line-strong px-3 py-1.5 font-mono text-xs text-ink transition-colors hover:bg-surface"
    >
      Reindex
    </button>
  );
}

function SettledMessage({ job }: { job: JobOut }) {
  if (job.status === "done") {
    return <p className="font-mono text-xs text-success">Reindex complete.</p>;
  }
  if (job.status === "cancelled") {
    return <p className="font-mono text-xs text-muted">Reindex cancelled.</p>;
  }
  return (
    <p role="alert" className="font-mono text-xs text-error">
      {job.error ?? "Reindex failed."}
    </p>
  );
}

function ReindexProgress({ job, cancelling }: { job: JobOut; cancelling: boolean }) {
  const pct =
    job.total_chunks !== null && job.total_chunks > 0
      ? Math.min(100, Math.round((job.embedded_chunks / job.total_chunks) * 100))
      : null;

  return (
    <div className="flex min-w-[180px] flex-col gap-1">
      {pct !== null && (
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Reindexing ${job.repo}`}
          className="h-1.5 w-full overflow-hidden rounded-full bg-line"
        >
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      <span aria-live="polite" className="font-mono text-xs text-muted">
        {cancelling ? "Cancelling… " : ""}
        {pct !== null
          ? `${job.embedded_chunks} / ${job.total_chunks} chunks (${pct}%)`
          : `${job.embedded_chunks} chunks embedded so far…`}
      </span>
    </div>
  );
}
