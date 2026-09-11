import type { Citation } from "./types";

/** `repo/file_path:start-end`, or `repo/file_path:line` when it's one line. */
export function formatCitationLabel(citation: Citation): string {
  const lines =
    citation.start_line === citation.end_line
      ? `${citation.start_line}`
      : `${citation.start_line}-${citation.end_line}`;
  return `${citation.repo}/${citation.file_path}:${lines}`;
}
