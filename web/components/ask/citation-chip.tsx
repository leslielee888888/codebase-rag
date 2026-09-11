"use client";

import { useId, useState } from "react";
import { ApiError, fetchCitationSnippet } from "@/lib/api";
import { formatCitationLabel } from "@/lib/format";
import type { Citation } from "@/lib/types";

interface CitationChipProps {
  citation: Citation;
}

type SnippetState =
  | { status: "collapsed" }
  | { status: "loading" }
  | { status: "loaded"; content: string }
  | { status: "error"; message: string };

/**
 * One citation pill (FR-1/FR-3). Clicking it fetches and shows the exact
 * retrieved snippet inline via `GET /citation`; clicking again collapses
 * it. State is self-contained — each chip fetches independently, so
 * several can be expanded across a thread at once.
 */
export function CitationChip({ citation }: CitationChipProps) {
  const [snippet, setSnippet] = useState<SnippetState>({ status: "collapsed" });
  const panelId = useId();
  const isExpanded = snippet.status !== "collapsed";

  async function toggle() {
    if (isExpanded) {
      setSnippet({ status: "collapsed" });
      return;
    }
    setSnippet({ status: "loading" });
    try {
      const content = await fetchCitationSnippet({
        repo: citation.repo,
        file_path: citation.file_path,
        start_line: citation.start_line,
        end_line: citation.end_line,
      });
      setSnippet({ status: "loaded", content });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Couldn't load this snippet.";
      setSnippet({ status: "error", message });
    }
  }

  return (
    <div className="inline-flex flex-col align-top">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={isExpanded}
        aria-controls={panelId}
        className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 font-mono text-xs text-accent transition-colors hover:bg-accent/20"
      >
        <span aria-hidden="true">[{citation.index}]</span>
        <span>{formatCitationLabel(citation)}</span>
      </button>
      {isExpanded && (
        <div
          id={panelId}
          className="mt-2 max-w-full overflow-x-auto rounded-md border border-line bg-well p-3"
        >
          {snippet.status === "loading" && (
            <p className="font-mono text-xs text-muted">Loading snippet…</p>
          )}
          {snippet.status === "error" && (
            <p className="font-mono text-xs text-error">{snippet.message}</p>
          )}
          {snippet.status === "loaded" && (
            <pre className="font-mono text-xs leading-relaxed text-ink">
              <code>{snippet.content}</code>
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
