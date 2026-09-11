import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, askQuestion, fetchCitationSnippet, fetchRepos } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchRepos", () => {
  it("returns the repos array from GET /repos", async () => {
    const repos = [{ name: "codebase-rag", path: "/repos/codebase-rag", indexed: true, last_indexed_at: "2026-09-01T00:00:00Z" }];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ repos }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchRepos()).resolves.toEqual(repos);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/repos$/),
      expect.objectContaining({ signal: undefined }),
    );
  });

  it("throws an ApiError carrying the API's detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "config.yaml not found" }, 400)),
    );

    await expect(fetchRepos()).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      message: "config.yaml not found",
    });
  });

  it("throws a friendly ApiError when the network request itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    await expect(fetchRepos()).rejects.toBeInstanceOf(ApiError);
    await expect(fetchRepos()).rejects.toMatchObject({ status: 0 });
  });
});

describe("askQuestion", () => {
  it("POSTs question/repos/history and returns the parsed answer", async () => {
    const response = { answer: "It does X.", citations: [], latency_ms: 1200 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);

    const result = await askQuestion({
      question: "how does X work?",
      repos: ["codebase-rag"],
      history: [["prior q", "prior a"]],
    });

    expect(result).toEqual(response);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      question: "how does X work?",
      repos: ["codebase-rag"],
      history: [["prior q", "prior a"]],
    });
  });

  it("omits repos/history from the body when empty (scope = all repos)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ answer: "ok", citations: [], latency_ms: 5 }));
    vi.stubGlobal("fetch", fetchMock);

    await askQuestion({ question: "q", repos: [], history: [] });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.repos).toBeUndefined();
    expect(body.history).toBeUndefined();
  });

  it("maps a 409 (nothing indexed) response to an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Nothing indexed yet." }, 409)),
    );

    await expect(askQuestion({ question: "q" })).rejects.toMatchObject({
      status: 409,
      message: "Nothing indexed yet.",
    });
  });
});

describe("fetchCitationSnippet", () => {
  it("requests the citation with the right query params and returns its content", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ content: "def foo(): ..." }));
    vi.stubGlobal("fetch", fetchMock);

    const content = await fetchCitationSnippet({
      repo: "codebase-rag",
      file_path: "src/foo.py",
      start_line: 10,
      end_line: 20,
    });

    expect(content).toBe("def foo(): ...");
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("repo=codebase-rag");
    expect(url).toContain("file_path=src%2Ffoo.py");
    expect(url).toContain("start_line=10");
    expect(url).toContain("end_line=20");
  });

  it("throws an ApiError on a 404 (reindexed since)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "No such citation - the repo may have been reindexed since." }, 404),
      ),
    );

    await expect(
      fetchCitationSnippet({ repo: "r", file_path: "f", start_line: 1, end_line: 2 }),
    ).rejects.toMatchObject({ status: 404 });
  });
});
