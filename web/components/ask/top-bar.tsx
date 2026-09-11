import type { ReactNode } from "react";

interface TopBarProps {
  title: string;
  children?: ReactNode;
}

/** View title + (optionally) the scope selector, per PRD §7's layout. */
export function TopBar({ title, children }: TopBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
      <h1 className="font-mono text-sm font-semibold text-ink">{title}</h1>
      {children}
    </div>
  );
}
