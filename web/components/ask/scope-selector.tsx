"use client";

import type { RepoInfo } from "@/lib/types";

interface ScopeSelectorProps {
  repos: RepoInfo[];
  /** Selected repo names. Empty means "all repos" (FR-2). */
  selected: string[];
  onChange: (next: string[]) => void;
}

/**
 * Scopes a question to one, several, or all indexed repos (FR-2). An empty
 * selection means "all" — the same thing omitting `repos` means to the API.
 */
export function ScopeSelector({ repos, selected, onChange }: ScopeSelectorProps) {
  const isAll = selected.length === 0;

  function toggleRepo(name: string) {
    if (selected.includes(name)) {
      onChange(selected.filter((repo) => repo !== name));
    } else {
      onChange([...selected, name]);
    }
  }

  return (
    <div role="group" aria-label="Scope this question to" className="flex flex-wrap gap-2">
      <ScopeChip label="All repos" active={isAll} onClick={() => onChange([])} />
      {repos.map((repo) => (
        <ScopeChip
          key={repo.name}
          label={repo.name}
          active={selected.includes(repo.name)}
          indexed={repo.indexed}
          onClick={() => toggleRepo(repo.name)}
        />
      ))}
    </div>
  );
}

interface ScopeChipProps {
  label: string;
  active: boolean;
  indexed?: boolean;
  onClick: () => void;
}

function ScopeChip({ label, active, indexed, onClick }: ScopeChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs transition-colors ${
        active
          ? "border-accent bg-accent/15 text-accent"
          : "border-line text-muted hover:border-line-strong hover:text-ink"
      }`}
    >
      {indexed !== undefined && (
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${indexed ? "bg-success" : "bg-faint"}`}
        />
      )}
      {label}
      {indexed === false && <span className="text-faint">(not indexed)</span>}
    </button>
  );
}
