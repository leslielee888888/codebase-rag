"use client";

import { useId, useState } from "react";
import { formatRelativeTime, formatSourceLabel } from "@/lib/format";
import type { HistoryEntry } from "@/lib/types";

interface HistoryEntryRowProps {
  entry: HistoryEntry;
}

/**
 * One past question (FR-7). Clicking it reveals the actual stored answer
 * already present in the `GET /history` response — no second API call.
 * `answer` is `null` for a pre-migration legacy row (§10 Q7, logged before
 * the `answer`/`source` columns existed); that's shown as a plain message
 * rather than left to crash on a missing string.
 */
export function HistoryEntryRow({ entry }: HistoryEntryRowProps) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();

  return (
    <div className="rounded-lg border border-line bg-surface">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full flex-col items-start gap-1.5 px-4 py-3 text-left"
      >
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-xs text-muted">
            {formatRelativeTime(entry.asked_at)} · {formatSourceLabel(entry.source)}
          </span>
          {entry.repos.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {entry.repos.map((repo) => (
                <span
                  key={repo}
                  className="inline-flex items-center rounded-full border border-line px-2.5 py-0.5 font-mono text-[11px] text-muted"
                >
                  {repo}
                </span>
              ))}
            </div>
          )}
        </div>
        <p className="text-sm text-ink">{entry.question}</p>
      </button>
      {expanded && (
        <div id={panelId} className="border-t border-line px-4 py-3">
          <p className="font-mono text-xs text-accent">codebase-rag</p>
          {entry.answer !== null ? (
            <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
              {entry.answer}
            </p>
          ) : (
            <p className="mt-1 text-sm text-faint">
              — no answer recorded (logged before this was tracked)
            </p>
          )}
        </div>
      )}
    </div>
  );
}
