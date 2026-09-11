import { NavLink } from "./nav-link";

/**
 * The dashboard's persistent left nav (PRD §7). Static apart from the
 * active-link highlight, which `NavLink` handles on its own — this stays a
 * Server Component. "Repos" and "History" route to real placeholder pages
 * (T8/T10 build them out) rather than being inert links.
 */
export function Sidebar() {
  return (
    <aside className="flex w-[232px] shrink-0 flex-col border-r border-line bg-well">
      <div className="border-b border-line px-5 py-5">
        <span className="font-mono text-sm font-semibold tracking-wide text-ink">
          codebase<span className="text-accent">-rag</span>
        </span>
      </div>
      <nav aria-label="Main" className="flex flex-col gap-1 p-3">
        <NavLink href="/">Ask</NavLink>
        <NavLink href="/repos">Repos</NavLink>
        <NavLink href="/history">History</NavLink>
      </nav>
    </aside>
  );
}
