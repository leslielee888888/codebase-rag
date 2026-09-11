import type { Citation } from "./types";

/** `repo/file_path:start-end`, or `repo/file_path:line` when it's one line. */
export function formatCitationLabel(citation: Citation): string {
  const lines =
    citation.start_line === citation.end_line
      ? `${citation.start_line}`
      : `${citation.start_line}-${citation.end_line}`;
  return `${citation.repo}/${citation.file_path}:${lines}`;
}

const RELATIVE_TIME_DIVISIONS: { unit: Intl.RelativeTimeFormatUnit; amount: number }[] = [
  { unit: "second", amount: 60 },
  { unit: "minute", amount: 60 },
  { unit: "hour", amount: 24 },
  { unit: "day", amount: 30 },
  { unit: "month", amount: 12 },
  { unit: "year", amount: Infinity },
];

/**
 * A repo's `last_indexed_at` (FR-4) as relative time — "5 minutes ago", "2
 * hours ago", etc. — via the built-in `Intl.RelativeTimeFormat` rather than
 * a date library, since this is the only place the app needs one.
 */
export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  let duration = (new Date(iso).getTime() - now) / 1000;

  for (const { unit, amount } of RELATIVE_TIME_DIVISIONS) {
    if (Math.abs(duration) < amount) {
      return rtf.format(Math.round(duration), unit);
    }
    duration /= amount;
  }
  return rtf.format(Math.round(duration), "year");
}
