"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (question: string) => void;
}

/** The pinned-to-bottom question input (FR-1). */
export function Composer({ disabled, onSubmit }: ComposerProps) {
  const [value, setValue] = useState("");

  function submit() {
    const question = value.trim();
    if (question.length === 0 || disabled) return;
    onSubmit(question);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // `isComposing` (and the legacy keyCode 229 fallback some browsers still
    // need) means this Enter is committing an IME composition candidate —
    // e.g. typing Japanese/Chinese/Korean — not a request to submit. Without
    // this guard, that Enter both commits the candidate *and* sends the
    // half-typed question.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 border-t border-line bg-surface px-6 py-4"
    >
      <label htmlFor="composer-input" className="sr-only">
        Ask a question about your indexed repos
      </label>
      <textarea
        id="composer-input"
        rows={1}
        value={value}
        disabled={disabled}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about your indexed repos…"
        className="max-h-40 min-h-10 flex-1 resize-none rounded-md border border-line bg-well px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={disabled || value.trim().length === 0}
        className="rounded-md bg-accent px-4 py-2 font-mono text-sm font-medium text-canvas transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Send
      </button>
    </form>
  );
}
