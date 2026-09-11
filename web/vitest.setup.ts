import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL's auto-cleanup only self-registers when it detects global test hooks;
// this project runs Vitest with `globals: false`, so wire it up explicitly —
// otherwise DOM from one test (e.g. render(<ScopeSelector .../>)) leaks into
// the next and queries like getByRole start matching more than one element.
afterEach(() => {
  cleanup();
});

// jsdom doesn't implement scrollIntoView (Thread's auto-scroll effect calls
// it on every new turn) — stub it so effects don't throw during tests.
if (typeof window !== "undefined" && !window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {};
}
