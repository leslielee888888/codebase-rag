"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

interface NavLinkProps {
  href: string;
  children: ReactNode;
}

/**
 * A sidebar nav item that highlights itself when active. Isolated as its
 * own client component (rather than making the whole Sidebar client) since
 * `usePathname` is the only piece of this UI that needs the browser.
 */
export function NavLink({ href, children }: NavLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={`rounded px-3 py-2 font-mono text-sm transition-colors ${
        isActive
          ? "bg-surface text-accent"
          : "text-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}
