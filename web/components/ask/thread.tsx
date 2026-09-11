"use client";

import { useEffect, useRef } from "react";
import { MessageTurn } from "./message-turn";
import type { ChatTurn } from "./chat-turn";

interface ThreadProps {
  turns: ChatTurn[];
  pendingQuestion: string | null;
  onRetry: (turn: ChatTurn) => void;
}

/** The scrollable conversation area — auto-scrolls to the newest turn. */
export function Thread({ turns, pendingQuestion, onRetry }: ThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const turnCount = turns.length;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
    // Re-run per new turn or when a pending question appears, not on every
    // turns-array identity change.
  }, [turnCount, pendingQuestion]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        {turns.map((turn) => (
          <MessageTurn key={turn.id} turn={turn} onRetry={onRetry} />
        ))}
        {pendingQuestion !== null && (
          <div className="flex flex-col gap-3">
            <div className="self-end max-w-[80%] rounded-lg bg-surface px-4 py-2.5">
              <p className="font-mono text-xs text-muted">You</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{pendingQuestion}</p>
            </div>
            <div
              role="status"
              aria-live="polite"
              className="flex max-w-[85%] items-center gap-2 rounded-lg border border-line bg-surface px-4 py-3"
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 animate-pulse rounded-full bg-accent"
              />
              <p className="font-mono text-xs text-muted">Thinking…</p>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
