import type { HistoryEntry } from "@/lib/types";
import { HistoryEntryRow } from "./history-entry-row";

interface HistoryListProps {
  /** Newest first — the order `GET /history` already returns them in. */
  entries: HistoryEntry[];
}

/** The recent-questions list half of FR-7. */
export function HistoryList({ entries }: HistoryListProps) {
  return (
    <ul className="flex flex-col gap-2">
      {entries.map((entry) => (
        <li key={entry.id}>
          <HistoryEntryRow entry={entry} />
        </li>
      ))}
    </ul>
  );
}
