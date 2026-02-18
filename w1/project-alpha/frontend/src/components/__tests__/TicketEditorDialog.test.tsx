import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TicketEditorDialog } from "@/components/TicketEditorDialog";

describe("TicketEditorDialog", () => {
  it("validates title before submit", async () => {
    const onSubmit = vi.fn();

    render(
      <TicketEditorDialog
        open
        mode="create"
        tags={[]}
        initialValue={null}
        isSaving={false}
        onClose={() => undefined}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Create Ticket" }));

    expect(await screen.findByText("Title is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits normalized payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(
      <TicketEditorDialog
        open
        mode="create"
        tags={[{ id: 1, name: "backend", created_at: "", updated_at: "" }]}
        initialValue={null}
        isSaving={false}
        onClose={() => undefined}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "  Ship feature  " } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "  Summary  " } });
    fireEvent.click(screen.getByRole("button", { name: "backend" }));
    fireEvent.click(screen.getByRole("button", { name: "Create Ticket" }));

    expect(onSubmit).toHaveBeenCalledWith({
      title: "Ship feature",
      description: "Summary",
      tag_ids: [1],
    });
  });
});
