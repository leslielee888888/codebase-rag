import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RepoRow } from "./repo-row";
import { ApiError } from "@/lib/api";
import type { RepoInfo } from "@/lib/types";

const { fetchReindexStatusMock, triggerReindexMock, cancelReindexMock, removeRepoMock } = vi.hoisted(() => ({
  fetchReindexStatusMock: vi.fn(),
  triggerReindexMock: vi.fn(),
  cancelReindexMock: vi.fn(),
  removeRepoMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchReindexStatus: fetchReindexStatusMock,
    triggerReindex: triggerReindexMock,
    cancelReindex: cancelReindexMock,
    removeRepo: removeRepoMock,
  };
});

const indexedRepo: RepoInfo = {
  name: "codebase-rag",
  path: "/repos/codebase-rag",
  indexed: true,
  last_indexed_at: "2026-01-01T00:00:00Z",
};

const unindexedRepo: RepoInfo = {
  name: "ai-docs",
  path: "/repos/ai-docs",
  indexed: false,
  last_indexed_at: null,
};

// Tiny so tests don't wait on the real 2s production cadence.
const POLL_MS = 15;

describe("RepoRow", () => {
  beforeEach(() => {
    // Each mock's queued/default return values must not leak between tests
    // — a later test's un-configured call (e.g. a background poll firing
    // after the test's own assertions) would otherwise silently resolve
    // with a PRIOR test's leftover mock value instead of failing loudly.
    fetchReindexStatusMock.mockReset();
    triggerReindexMock.mockReset();
    cancelReindexMock.mockReset();
    removeRepoMock.mockReset();
  });

  it("FR-4: shows Not indexed for a repo that's never been reindexed", async () => {
    fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found for 'ai-docs'."));
    render(
      <table>
        <tbody>
          <RepoRow repo={unindexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );

    expect(await screen.findByText("Not indexed")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reindex/i })).toBeInTheDocument();
  });

  it("surfaces a real failure checking reindex status on mount, instead of silently rendering idle", async () => {
    fetchReindexStatusMock.mockRejectedValue(new ApiError(502, "Couldn't reach the codebase-rag API."));
    render(
      <table>
        <tbody>
          <RepoRow repo={unindexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach the codebase-rag API.");
    // Still offers a way to retry, rather than a dead end.
    expect(screen.getByRole("button", { name: /reindex/i })).toBeInTheDocument();
  });

  it("FR-4: shows Indexed with a relative last-indexed time", async () => {
    fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
    render(
      <table>
        <tbody>
          <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );

    expect(await screen.findByText("Indexed")).toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
  });

  it("FR-5a: triggering a reindex shows real, incrementing progress (not just a spinner)", async () => {
    fetchReindexStatusMock.mockRejectedValueOnce(new ApiError(404, "No reindex job found."));
    const onReindexed = vi.fn();
    render(
      <table>
        <tbody>
          <RepoRow repo={unindexedRepo} onReindexed={onReindexed} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );
    await screen.findByRole("button", { name: /reindex/i });

    triggerReindexMock.mockResolvedValue({
      job_id: 1,
      repo: "ai-docs",
      status: "running",
      total_chunks: null,
      embedded_chunks: 0,
      cancel_requested: false,
      error: null,
    });
    fireEvent.click(screen.getByRole("button", { name: /reindex/i }));

    expect(await screen.findByText(/0 chunks embedded so far/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();

    fetchReindexStatusMock.mockResolvedValueOnce({
      job_id: 1,
      repo: "ai-docs",
      status: "running",
      total_chunks: 100,
      embedded_chunks: 40,
      cancel_requested: false,
      error: null,
    });

    await waitFor(() => expect(screen.getByText("40 / 100 chunks (40%)")).toBeInTheDocument());
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "40");

    fetchReindexStatusMock.mockResolvedValue({
      job_id: 1,
      repo: "ai-docs",
      status: "done",
      total_chunks: 100,
      embedded_chunks: 100,
      cancel_requested: false,
      error: null,
    });

    await waitFor(() => expect(screen.getByText("Reindex complete.")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /reindex/i })).toBeInTheDocument();
    expect(onReindexed).toHaveBeenCalled();
  });

  it("FR-5b: a 409 from trigger (already reindexing) surfaces the backend's message clearly", async () => {
    fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
    render(
      <table>
        <tbody>
          <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );
    await screen.findByRole("button", { name: /reindex/i });

    triggerReindexMock.mockRejectedValue(
      new ApiError(409, "'codebase-rag' is already reindexing."),
    );
    fireEvent.click(screen.getByRole("button", { name: /reindex/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("'codebase-rag' is already reindexing.");
    // Not fatal/blocking — the reindex control is still usable.
    expect(screen.getByRole("button", { name: /reindex/i })).toBeInTheDocument();
  });

  it("FR-5c: cancelling is reflected only once the job actually stops", async () => {
    fetchReindexStatusMock.mockRejectedValueOnce(new ApiError(404, "No reindex job found."));
    render(
      <table>
        <tbody>
          <RepoRow repo={unindexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );
    await screen.findByRole("button", { name: /reindex/i });

    triggerReindexMock.mockResolvedValue({
      job_id: 2,
      repo: "ai-docs",
      status: "running",
      total_chunks: 10,
      embedded_chunks: 2,
      cancel_requested: false,
      error: null,
    });
    fireEvent.click(screen.getByRole("button", { name: /reindex/i }));
    await screen.findByRole("button", { name: /cancel/i });

    cancelReindexMock.mockResolvedValue({
      job_id: 2,
      repo: "ai-docs",
      status: "running",
      total_chunks: 10,
      embedded_chunks: 3,
      cancel_requested: true,
      error: null,
    });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    // Still running (cancellation stops at the next checkpoint) — no
    // "cancelled" outcome yet, and the Cancel button is no longer offered
    // since cancellation was already requested.
    expect(await screen.findByText(/cancelling…/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^cancel$/i })).not.toBeInTheDocument();

    fetchReindexStatusMock.mockResolvedValue({
      job_id: 2,
      repo: "ai-docs",
      status: "cancelled",
      total_chunks: 10,
      embedded_chunks: 4,
      cancel_requested: true,
      error: null,
    });

    await waitFor(() => expect(screen.getByText("Reindex cancelled.")).toBeInTheDocument());
  });

  it("a 409 from cancel (not actually running) surfaces the message without blocking the UI", async () => {
    fetchReindexStatusMock.mockRejectedValueOnce(new ApiError(404, "No reindex job found."));
    render(
      <table>
        <tbody>
          <RepoRow repo={unindexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );
    await screen.findByRole("button", { name: /reindex/i });

    triggerReindexMock.mockResolvedValue({
      job_id: 3,
      repo: "ai-docs",
      status: "running",
      total_chunks: null,
      embedded_chunks: 0,
      cancel_requested: false,
      error: null,
    });
    fireEvent.click(screen.getByRole("button", { name: /reindex/i }));
    await screen.findByRole("button", { name: /cancel/i });

    cancelReindexMock.mockRejectedValue(new ApiError(409, "'ai-docs' isn't currently reindexing."));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("'ai-docs' isn't currently reindexing.");
    expect(screen.getByRole("button", { name: /reindex/i })).toBeInTheDocument();
  });

  it("picks up an already-running job discovered on mount", async () => {
    fetchReindexStatusMock.mockResolvedValueOnce({
      job_id: 4,
      repo: "codebase-rag",
      status: "running",
      total_chunks: 50,
      embedded_chunks: 10,
      cancel_requested: false,
      error: null,
    });
    render(
      <table>
        <tbody>
          <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
        </tbody>
      </table>,
    );

    expect(await screen.findByText("10 / 50 chunks (20%)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  describe("remove (FR-8b)", () => {
    it("requires confirmation before calling DELETE /repos/{repo}", async () => {
      fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
      const onRemoved = vi.fn();
      render(
        <table>
          <tbody>
            <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={onRemoved} pollIntervalMs={POLL_MS} />
          </tbody>
        </table>,
      );
      await screen.findByRole("button", { name: /^remove$/i });

      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
      expect(screen.getByText(/remove "codebase-rag"\?/i)).toBeInTheDocument();
      expect(removeRepoMock).not.toHaveBeenCalled();

      removeRepoMock.mockResolvedValue(undefined);
      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

      await waitFor(() => expect(removeRepoMock).toHaveBeenCalledWith("codebase-rag"));
      await waitFor(() => expect(onRemoved).toHaveBeenCalled());
    });

    it("backs out of the confirm step on Cancel without calling DELETE", async () => {
      fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
      render(
        <table>
          <tbody>
            <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
          </tbody>
        </table>,
      );
      await screen.findByRole("button", { name: /^remove$/i });

      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

      expect(screen.queryByText(/remove "codebase-rag"\?/i)).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^remove$/i })).toBeInTheDocument();
      expect(removeRepoMock).not.toHaveBeenCalled();
    });

    it("surfaces a 404 (already gone) clearly and leaves the row usable", async () => {
      fetchReindexStatusMock.mockRejectedValue(new ApiError(404, "No reindex job found."));
      render(
        <table>
          <tbody>
            <RepoRow repo={indexedRepo} onReindexed={vi.fn()} onRemoved={vi.fn()} pollIntervalMs={POLL_MS} />
          </tbody>
        </table>,
      );
      await screen.findByRole("button", { name: /^remove$/i });

      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
      removeRepoMock.mockRejectedValue(new ApiError(404, "'codebase-rag' isn't in config.yaml."));
      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent("'codebase-rag' isn't in config.yaml.");
      expect(screen.getByRole("button", { name: /^remove$/i })).toBeInTheDocument();
    });

    it("removing a repo mid-reindex doesn't crash — the row simply unmounts on the next parent refresh", async () => {
      fetchReindexStatusMock.mockRejectedValueOnce(new ApiError(404, "No reindex job found."));
      const onRemoved = vi.fn();
      const { unmount } = render(
        <table>
          <tbody>
            <RepoRow repo={unindexedRepo} onReindexed={vi.fn()} onRemoved={onRemoved} pollIntervalMs={POLL_MS} />
          </tbody>
        </table>,
      );
      await screen.findByRole("button", { name: /reindex/i });

      triggerReindexMock.mockResolvedValue({
        job_id: 5,
        repo: "ai-docs",
        status: "running",
        total_chunks: null,
        embedded_chunks: 0,
        cancel_requested: false,
        error: null,
      });
      fireEvent.click(screen.getByRole("button", { name: /reindex/i }));
      await screen.findByRole("button", { name: /cancel/i });

      removeRepoMock.mockResolvedValue(undefined);
      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
      fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
      await waitFor(() => expect(onRemoved).toHaveBeenCalled());

      // Simulates the parent dropping this row once its refetch settles
      // (the real trigger for this unmount) — the row's own poll-cleanup
      // effect must not throw when torn down mid-poll.
      expect(() => unmount()).not.toThrow();
    });
  });
});
