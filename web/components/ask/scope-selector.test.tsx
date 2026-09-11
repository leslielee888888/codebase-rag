import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ScopeSelector } from "./scope-selector";
import type { RepoInfo } from "@/lib/types";

const repos: RepoInfo[] = [
  { name: "codebase-rag", path: "/a", indexed: true, last_indexed_at: "2026-01-01T00:00:00Z" },
  { name: "ai-docs", path: "/b", indexed: false, last_indexed_at: null },
];

describe("ScopeSelector", () => {
  it("defaults to All repos selected (empty scope)", () => {
    render(<ScopeSelector repos={repos} selected={[]} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /all repos/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("selecting a repo adds it to the scope", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ScopeSelector repos={repos} selected={[]} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /codebase-rag/i }));

    expect(onChange).toHaveBeenCalledWith(["codebase-rag"]);
  });

  it("deselecting a chosen repo removes it from the scope", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ScopeSelector repos={repos} selected={["codebase-rag"]} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /codebase-rag/i }));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("clicking All repos clears the scope", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ScopeSelector repos={repos} selected={["codebase-rag"]} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: /all repos/i }));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("marks an unindexed repo as not indexed", () => {
    render(<ScopeSelector repos={repos} selected={[]} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /ai-docs/i })).toHaveTextContent("not indexed");
  });
});
