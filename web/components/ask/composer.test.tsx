import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "./composer";

describe("Composer", () => {
  it("submits the trimmed question and clears the input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer disabled={false} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/ask a question/i);
    await user.type(input, "  how does X work?  ");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).toHaveBeenCalledWith("how does X work?");
    expect(input).toHaveValue("");
  });

  it("submits on Enter without Shift", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer disabled={false} onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/ask a question/i), "hello{Enter}");

    expect(onSubmit).toHaveBeenCalledWith("hello");
  });

  it("does not submit on the Enter that commits an IME composition", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer disabled={false} onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/ask a question/i);
    await user.type(input, "こんにちは");
    // Simulates the Enter a Japanese/Chinese/Korean IME sends to commit a
    // composition candidate — userEvent has no built-in way to flag this,
    // so it's dispatched directly with `isComposing: true` on the native
    // event, the same signal a real browser sends.
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });

    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveValue("こんにちは");
  });

  it("does not submit an empty question", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Composer disabled={false} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables the input and button while a query is in flight", () => {
    render(<Composer disabled={true} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText(/ask a question/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
