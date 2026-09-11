import type { Citation } from "@/lib/types";

/**
 * One turn in the Ask thread's local (ephemeral, per PRD §10 Q8) state.
 * Only `"answered"` turns are ever sent back as `history` (FR-6) — a
 * turn that errored never happened as far as the model is concerned.
 */
export type ChatTurn =
  | { id: string; status: "answered"; question: string; answer: string; citations: Citation[] }
  | { id: string; status: "error"; question: string; message: string };
