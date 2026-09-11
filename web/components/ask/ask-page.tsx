"use client";

import { useState } from "react";
import { ApiError, askQuestion, fetchRepos } from "@/lib/api";
import type { RepoInfo, Turn } from "@/lib/types";
import { Composer } from "./composer";
import { EmptyState } from "./empty-state";
import { ReposLoadError } from "./repos-load-error";
import { ScopeSelector } from "./scope-selector";
import { Thread } from "./thread";
import { TopBar } from "./top-bar";
import type { ChatTurn } from "./chat-turn";

interface AskPageProps {
  /** Seeded from a server-side `GET /repos` call — `null` if that failed. */
  initialRepos: RepoInfo[] | null;
  initialReposError: string | null;
}

function newTurnId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** The Ask/chat view (FR-1, FR-2, FR-3, FR-6) — this task's whole surface. */
export function AskPage({ initialRepos, initialReposError }: AskPageProps) {
  const [repos, setRepos] = useState<RepoInfo[]>(initialRepos ?? []);
  const [reposError, setReposError] = useState<string | null>(initialReposError);
  const [reposRetrying, setReposRetrying] = useState(false);
  const [scope, setScope] = useState<string[]>([]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  async function retryRepos() {
    setReposRetrying(true);
    try {
      const next = await fetchRepos();
      setRepos(next);
      setReposError(null);
    } catch (error) {
      setReposError(error instanceof ApiError ? error.message : "Something went wrong.");
    } finally {
      setReposRetrying(false);
    }
  }

  async function handleAsk(question: string) {
    setPendingQuestion(question);
    const history: Turn[] = turns
      .filter((turn) => turn.status === "answered")
      .map((turn) => [turn.question, turn.answer]);

    try {
      const result = await askQuestion({ question, repos: scope, history });
      setTurns((prev) => [
        ...prev,
        {
          id: newTurnId(),
          status: "answered",
          question,
          answer: result.answer,
          citations: result.citations,
        },
      ]);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Something went wrong asking that.";
      setTurns((prev) => [...prev, { id: newTurnId(), status: "error", question, message }]);
    } finally {
      setPendingQuestion(null);
    }
  }

  function handleRetry(turn: ChatTurn) {
    if (turn.status !== "error") return;
    setTurns((prev) => prev.filter((existing) => existing.id !== turn.id));
    void handleAsk(turn.question);
  }

  if (reposError !== null && repos.length === 0) {
    return <ReposLoadError message={reposError} onRetry={retryRepos} retrying={reposRetrying} />;
  }

  if (repos.length === 0) {
    return <EmptyState />;
  }

  return (
    <>
      <TopBar title="Ask">
        <ScopeSelector repos={repos} selected={scope} onChange={setScope} />
      </TopBar>
      <Thread turns={turns} pendingQuestion={pendingQuestion} onRetry={handleRetry} />
      <Composer disabled={pendingQuestion !== null} onSubmit={handleAsk} />
    </>
  );
}
