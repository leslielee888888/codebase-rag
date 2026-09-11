import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AddRepoForm } from "./add-repo-form";
import { ApiError } from "@/lib/api";

const { addRepoMock } = vi.hoisted(() => ({ addRepoMock: vi.fn() }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, addRepo: addRepoMock };
});

describe("AddRepoForm", () => {
  it("FR-8a: submits name/path, calls onAdded, and clears the form", async () => {
    const user = userEvent.setup();
    addRepoMock.mockResolvedValue({
      name: "ai-docs",
      path: "/repos/ai-docs",
      indexed: false,
      last_indexed_at: null,
    });
    const onAdded = vi.fn();
    render(<AddRepoForm onAdded={onAdded} />);

    await user.type(screen.getByLabelText(/name/i), "ai-docs");
    await user.type(screen.getByLabelText(/path/i), "/repos/ai-docs");
    await user.click(screen.getByRole("button", { name: /add repo/i }));

    expect(addRepoMock).toHaveBeenCalledWith({ name: "ai-docs", path: "/repos/ai-docs" });
    expect(onAdded).toHaveBeenCalled();
    expect(screen.getByLabelText(/name/i)).toHaveValue("");
    expect(screen.getByLabelText(/path/i)).toHaveValue("");
  });

  it("shows a client-side error instead of submitting when a field is blank", async () => {
    const user = userEvent.setup();
    const onAdded = vi.fn();
    render(<AddRepoForm onAdded={onAdded} />);

    await user.type(screen.getByLabelText(/name/i), "ai-docs");
    await user.click(screen.getByRole("button", { name: /add repo/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/both required/i);
    expect(addRepoMock).not.toHaveBeenCalled();
    expect(onAdded).not.toHaveBeenCalled();
  });

  it("surfaces a 409 (duplicate name) clearly and keeps the form usable", async () => {
    const user = userEvent.setup();
    addRepoMock.mockRejectedValue(new ApiError(409, "'ai-docs' is already configured."));
    const onAdded = vi.fn();
    render(<AddRepoForm onAdded={onAdded} />);

    await user.type(screen.getByLabelText(/name/i), "ai-docs");
    await user.type(screen.getByLabelText(/path/i), "/repos/ai-docs");
    await user.click(screen.getByRole("button", { name: /add repo/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("'ai-docs' is already configured.");
    expect(onAdded).not.toHaveBeenCalled();
    // Input isn't cleared on failure — nothing to retype.
    expect(screen.getByLabelText(/name/i)).toHaveValue("ai-docs");
  });

  it("surfaces a 422 (missing fields, from the backend) as an ApiError message", async () => {
    const user = userEvent.setup();
    addRepoMock.mockRejectedValue(new ApiError(422, "Request failed (422)."));
    render(<AddRepoForm onAdded={vi.fn()} />);

    await user.type(screen.getByLabelText(/name/i), "ai-docs");
    await user.type(screen.getByLabelText(/path/i), "/repos/ai-docs");
    await user.click(screen.getByRole("button", { name: /add repo/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/request failed \(422\)/i);
  });
});
