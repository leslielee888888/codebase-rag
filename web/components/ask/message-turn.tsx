import { CitationChip } from "./citation-chip";
import type { ChatTurn } from "./chat-turn";

interface MessageTurnProps {
  turn: ChatTurn;
  onRetry: (turn: ChatTurn) => void;
}

/** One question + its grounded answer (or its error) in the thread. */
export function MessageTurn({ turn, onRetry }: MessageTurnProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="self-end max-w-[80%] rounded-lg bg-surface px-4 py-2.5">
        <p className="font-mono text-xs text-muted">You</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{turn.question}</p>
      </div>

      {turn.status === "answered" ? (
        <div className="max-w-[85%] rounded-lg border border-line bg-surface px-4 py-3">
          <p className="font-mono text-xs text-accent">codebase-rag</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
            {turn.answer}
          </p>
          {turn.citations.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {turn.citations.map((citation) => (
                <CitationChip key={citation.index} citation={citation} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div
          role="alert"
          className="max-w-[85%] rounded-lg border border-error/40 bg-error/10 px-4 py-3"
        >
          <p className="font-mono text-xs text-error">Couldn&apos;t get an answer</p>
          <p className="mt-1 text-sm text-ink">{turn.message}</p>
          <button
            type="button"
            onClick={() => onRetry(turn)}
            className="mt-3 rounded border border-line-strong px-3 py-1.5 font-mono text-xs text-ink transition-colors hover:bg-well"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
