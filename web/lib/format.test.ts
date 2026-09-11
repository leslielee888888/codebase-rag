import { describe, expect, it } from "vitest";
import { formatRelativeTime } from "./format";

const NOW = new Date("2026-09-12T12:00:00Z").getTime();

describe("formatRelativeTime", () => {
  it("formats a few minutes ago", () => {
    expect(formatRelativeTime("2026-09-12T11:55:00Z", NOW)).toBe("5 minutes ago");
  });

  it("formats a few hours ago", () => {
    expect(formatRelativeTime("2026-09-12T09:00:00Z", NOW)).toBe("3 hours ago");
  });

  it("formats a few days ago", () => {
    expect(formatRelativeTime("2026-09-09T12:00:00Z", NOW)).toBe("3 days ago");
  });

  it("falls back to months once it's more than 30 days old", () => {
    expect(formatRelativeTime("2026-07-01T12:00:00Z", NOW)).toBe("2 months ago");
  });
});
