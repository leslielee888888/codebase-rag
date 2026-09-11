import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReposPage } from "./repos-page";
import { ApiError } from "@/lib/api";
import type { RepoInfo } from "@/lib/types";

const { fetchReposMock, fetchReindexStatusMock } = vi.hoisted(() => ({
  fetchReposMock: vi.fn(),
  fetchReindexStatusMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchRepos: fetchReposMock, fetchReindexStatus: fetchReindexStatusMock };
});

const repos: RepoInfo[] = [
  { name: "codebase-rag", path: "/a", indexed: true, last_indexed_at: "2026-01-01T00:00:00Z" },
  { name: "ai-docs", path: "/b", indexed: false, last_indexed_at: null },
];

describe("ReposPage", () => {
  it("shows the empty state when no repos are configured at all", () => {
    render(<ReposPage initialRepos={[]} initialReposError={null} />);
    expect(screen.getByText(/no repos configured yet/i)).toBeInTheDocument();
  });

  it("shows a load error with retry when the initial /repos call fails", async () => {
    const user = userEvent.setup();
    fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
    fetchReposMock.mockResolvedValueOnce(repos);
    render(<ReposPage initialRepos={null} initialReposError="Couldn't reach the API." />);

    expect(screen.getByText(/couldn't load your repos/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(screen.getByText("codebase-rag")).toBeInTheDocument());
  });

  it("FR-4: lists every configured repo with its indexed state", async () => {
    fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
    render(<ReposPage initialRepos={repos} initialReposError={null} />);

    expect(screen.getByText("codebase-rag")).toBeInTheDocument();
    expect(screen.getByText("ai-docs")).toBeInTheDocument();
    expect(await screen.findByText("Indexed")).toBeInTheDocument();
    expect(screen.getByText("Not indexed")).toBeInTheDocument();
  });
});
