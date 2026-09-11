import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CitationChip } from "./citation-chip";
import { ApiError } from "@/lib/api";
import type { Citation } from "@/lib/types";

const { fetchCitationSnippetMock } = vi.hoisted(() => ({
  fetchCitationSnippetMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchCitationSnippet: fetchCitationSnippetMock };
});

const citation: Citation = {
  index: 1,
  repo: "codebase-rag",
  file_path: "src/foo.py",
  start_line: 10,
  end_line: 12,
  citation: "[1]",
};

describe("CitationChip", () => {
  it("shows a compact repo/file:line label", () => {
    render(<CitationChip citation={citation} />);
    expect(screen.getByRole("button")).toHaveTextContent("codebase-rag/src/foo.py:10-12");
  });

  it("fetches and shows the exact snippet when clicked (FR-3)", async () => {
    const user = userEvent.setup();
    fetchCitationSnippetMock.mockResolvedValue("def foo():\n    return 1\n");
    render(<CitationChip citation={citation} />);

    await user.click(screen.getByRole("button"));

    expect(await screen.findByText(/def foo/)).toBeInTheDocument();
    expect(fetchCitationSnippetMock).toHaveBeenCalledWith({
      repo: "codebase-rag",
      file_path: "src/foo.py",
      start_line: 10,
      end_line: 12,
    });
  });

  it("collapses the snippet on a second click", async () => {
    const user = userEvent.setup();
    fetchCitationSnippetMock.mockResolvedValue("def foo(): ...");
    render(<CitationChip citation={citation} />);

    const button = screen.getByRole("button");
    await user.click(button);
    expect(await screen.findByText(/def foo/)).toBeInTheDocument();

    await user.click(button);
    expect(screen.queryByText(/def foo/)).not.toBeInTheDocument();
  });

  it("shows an error message if the snippet can't be loaded", async () => {
    const user = userEvent.setup();
    fetchCitationSnippetMock.mockRejectedValue(
      new ApiError(404, "No such citation - the repo may have been reindexed since."),
    );
    render(<CitationChip citation={citation} />);

    await user.click(screen.getByRole("button"));

    expect(await screen.findByText(/reindexed since/)).toBeInTheDocument();
  });
});
