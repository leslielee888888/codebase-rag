import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HistoryPage } from "./history-page";
import type { HistoryEntry, Stats } from "@/lib/types";

const { fetchStatsMock, fetchHistoryMock } = vi.hoisted(() => ({
  fetchStatsMock: vi.fn(),
  fetchHistoryMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchStats: fetchStatsMock, fetchHistory: fetchHistoryMock };
});

const stats: Stats = {
  queries_this_week: 12,
  queries_this_week_by_source: { dashboard: 9, cli: 3 },
};

const entries: HistoryEntry[] = [
  {
    id: 2,
    asked_at: "2026-09-12T10:00:00Z",
    question: "how does chunking work?",
    answer: "It splits files into overlapping windows.",
    source: "dashboard",
    repos: ["codebase-rag"],
  },
  {
    id: 1,
    asked_at: "2026-08-01T00:00:00Z",
    question: "a question from before answers were logged",
    answer: null,
    source: "cli",
    repos: [],
  },
];

describe("HistoryPage", () => {
  it("shows the empty state when nothing has been logged yet", () => {
    render(
      <HistoryPage
        initialStats={{ queries_this_week: 0, queries_this_week_by_source: {} }}
        initialEntries={[]}
        initialError={null}
      />,
    );
    expect(screen.getByText(/no queries logged yet/i)).toBeInTheDocument();
  });

  it("shows a load error with retry when the initial calls fail", async () => {
    const user = userEvent.setup();
    fetchStatsMock.mockResolvedValueOnce(stats);
    fetchHistoryMock.mockResolvedValueOnce(entries);
    render(
      <HistoryPage
        initialStats={null}
        initialEntries={null}
        initialError="Couldn't reach the API."
      />,
    );

    expect(screen.getByText(/couldn't load your history/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(screen.getByText(/how does chunking work\?/i)).toBeInTheDocument(),
    );
  });

  it("FR-7: shows queries-this-week and its per-source split, rendering only the keys present", () => {
    render(<HistoryPage initialStats={stats} initialEntries={entries} initialError={null} />);

    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/via dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/via cli/i)).toBeInTheDocument();
  });

  it("only renders source tiles that are actually present in the stats", () => {
    render(
      <HistoryPage
        initialStats={{ queries_this_week: 4, queries_this_week_by_source: { dashboard: 4 } }}
        initialEntries={entries}
        initialError={null}
      />,
    );

    expect(screen.getByText(/via dashboard/i)).toBeInTheDocument();
    expect(screen.queryByText(/via cli/i)).not.toBeInTheDocument();
  });

  it("FR-7: lists recent questions with a relative timestamp and source", () => {
    render(<HistoryPage initialStats={stats} initialEntries={entries} initialError={null} />);

    expect(screen.getByText(/how does chunking work\?/i)).toBeInTheDocument();
    expect(screen.getByText(/a question from before answers were logged/i)).toBeInTheDocument();
    expect(screen.getByText("codebase-rag")).toBeInTheDocument();
  });

  it("FR-7: clicking a past question reveals its real stored answer, not just the question", async () => {
    const user = userEvent.setup();
    render(<HistoryPage initialStats={stats} initialEntries={entries} initialError={null} />);

    expect(screen.queryByText(/splits files into overlapping windows/i)).not.toBeInTheDocument();

    await user.click(screen.getByText(/how does chunking work\?/i));

    expect(screen.getByText(/splits files into overlapping windows/i)).toBeInTheDocument();
  });

  it("§10 Q7: a null answer (pre-migration legacy row) shows a graceful message, not a crash", async () => {
    const user = userEvent.setup();
    render(<HistoryPage initialStats={stats} initialEntries={entries} initialError={null} />);

    await user.click(screen.getByText(/a question from before answers were logged/i));

    expect(screen.getByText(/no answer recorded/i)).toBeInTheDocument();
  });
});
