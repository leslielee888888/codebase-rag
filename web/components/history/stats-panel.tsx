import { formatSourceLabel } from "@/lib/format";
import type { Stats } from "@/lib/types";

interface StatsPanelProps {
  stats: Stats;
}

/**
 * Queries-this-week + per-source breakdown (FR-7, v1's §5 metric) — a
 * couple of stat tiles, no chart needed. A source key is only present in
 * `queries_this_week_by_source` once at least one query with that source
 * has been logged, so this renders whatever keys actually exist rather
 * than assuming both "dashboard" and "cli" are always there.
 */
export function StatsPanel({ stats }: StatsPanelProps) {
  const bySource = Object.entries(stats.queries_this_week_by_source).sort(
    ([, a], [, b]) => b - a,
  );

  return (
    <div className="flex flex-wrap gap-3">
      <StatTile label="Queries this week" value={stats.queries_this_week} />
      {bySource.map(([source, count]) => (
        <StatTile key={source} label={`via ${formatSourceLabel(source)}`} value={count} />
      ))}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-[160px] flex-1 rounded-lg border border-line bg-surface px-4 py-3">
      <p className="font-mono text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}
