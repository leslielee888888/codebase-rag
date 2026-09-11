import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AskPage } from "./ask-page";
import { ApiError } from "@/lib/api";
import type { RepoInfo } from "@/lib/types";

const { fetchReposMock, askQuestionMock } = vi.hoisted(() => ({
  fetchReposMock: vi.fn(),
  askQuestionMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchRepos: fetchReposMock, askQuestion: askQuestionMock };
});

const repos: RepoInfo[] = [
  { name: "codebase-rag", path: "/a", indexed: true, last_indexed_at: "2026-01-01T00:00:00Z" },
  { name: "ai-docs", path: "/b", indexed: true, last_indexed_at: "2026-01-01T00:00:00Z" },
];

describe("AskPage", () => {
  it("shows the empty state when no repos are configured at all", () => {
    render(<AskPage initialRepos={[]} initialReposError={null} />);
    expect(screen.getByText(/no repos configured yet/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/ask a question/i)).not.toBeInTheDocument();
  });

  it("shows a load error with retry when the initial /repos call fails", async () => {
    const user = userEvent.setup();
    fetchReposMock.mockResolvedValueOnce(repos);
    render(<AskPage initialRepos={null} initialReposError="Couldn't reach the API." />);

    expect(screen.getByText(/couldn't load your repos/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(screen.getByLabelText(/ask a question/i)).toBeInTheDocument());
  });

  it("FR-1: submitting a question shows a grounded answer with citations", async () => {
    const user = userEvent.setup();
    askQuestionMock.mockResolvedValue({
      answer: "It routes through answering.py.",
      citations: [
        {
          index: 1,
          repo: "codebase-rag",
          file_path: "src/codebase_rag/answering.py",
          start_line: 1,
          end_line: 5,
          citation: "[1]",
        },
      ],
      latency_ms: 900,
    });
    render(<AskPage initialRepos={repos} initialReposError={null} />);

    await user.type(screen.getByLabelText(/ask a question/i), "how does routing work?{Enter}");

    expect(await screen.findByText(/it routes through answering\.py/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /answering\.py:1-5/i }),
    ).toBeInTheDocument();
  });

  it("FR-2: a selected scope is sent as the repos list", async () => {
    const user = userEvent.setup();
    askQuestionMock.mockResolvedValue({ answer: "ok", citations: [], latency_ms: 5 });
    render(<AskPage initialRepos={repos} initialReposError={null} />);

    await user.click(screen.getByRole("button", { name: /^codebase-rag$/i }));
    await user.type(screen.getByLabelText(/ask a question/i), "a question{Enter}");

    await waitFor(() => expect(askQuestionMock).toHaveBeenCalled());
    expect(askQuestionMock.mock.calls[0][0]).toMatchObject({
      question: "a question",
      repos: ["codebase-rag"],
    });
  });

  it("FR-6: a follow-up question carries the prior turn as history", async () => {
    const user = userEvent.setup();
    askQuestionMock
      .mockResolvedValueOnce({ answer: "First answer.", citations: [], latency_ms: 5 })
      .mockResolvedValueOnce({ answer: "Second answer.", citations: [], latency_ms: 5 });
    render(<AskPage initialRepos={repos} initialReposError={null} />);

    await user.type(screen.getByLabelText(/ask a question/i), "first question{Enter}");
    await screen.findByText("First answer.");

    await user.type(screen.getByLabelText(/ask a question/i), "second question{Enter}");
    await screen.findByText("Second answer.");

    expect(askQuestionMock.mock.calls[1][0]).toMatchObject({
      question: "second question",
      history: [["first question", "First answer."]],
    });
  });

  it("Error state: a query failure is shown clearly with a retry affordance", async () => {
    const user = userEvent.setup();
    askQuestionMock
      .mockRejectedValueOnce(new ApiError(409, "Nothing indexed yet."))
      .mockResolvedValueOnce({ answer: "Now it works.", citations: [], latency_ms: 5 });
    render(<AskPage initialRepos={repos} initialReposError={null} />);

    await user.type(screen.getByLabelText(/ask a question/i), "a question{Enter}");

    expect(await screen.findByText("Nothing indexed yet.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByText("Now it works.")).toBeInTheDocument();
    expect(screen.queryByText("Nothing indexed yet.")).not.toBeInTheDocument();
  });
});
