import { useEffect, useMemo, useState } from "react";

import type { Tag, TicketPayload } from "@/types/api";

interface TicketEditorDialogProps {
  open: boolean;
  mode: "create" | "edit";
  tags: Tag[];
  initialValue?: {
    title: string;
    description: string | null;
    tagIds: number[];
  } | null;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (payload: TicketPayload) => Promise<void> | void;
}

export function TicketEditorDialog({
  open,
  mode,
  tags,
  initialValue,
  isSaving,
  onClose,
  onSubmit,
}: TicketEditorDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagIds, setTagIds] = useState<number[]>([]);
  const [titleError, setTitleError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setTitle(initialValue?.title ?? "");
    setDescription(initialValue?.description ?? "");
    setTagIds(initialValue?.tagIds ?? []);
    setTitleError(null);
  }, [open, initialValue]);

  const dialogTitle = useMemo(() => (mode === "create" ? "Create Ticket" : "Edit Ticket"), [mode]);

  if (!open) {
    return null;
  }

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedTitle = title.trim();
    if (!normalizedTitle) {
      setTitleError("Title is required.");
      return;
    }
    if (normalizedTitle.length > 200) {
      setTitleError("Title must be 200 characters or fewer.");
      return;
    }

    setTitleError(null);
    await onSubmit({
      title: normalizedTitle,
      description: description.trim() ? description.trim() : null,
      tag_ids: tagIds,
    });
  };

  const toggleTag = (tagId: number) => {
    setTagIds((previous) =>
      previous.includes(tagId) ? previous.filter((value) => value !== tagId) : [...previous, tagId],
    );
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4 dark:bg-slate-950/70">
      <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{dialogTitle}</h2>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-1.5">
            <label htmlFor="ticket-title" className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Title
            </label>
            <input
              id="ticket-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-cyan-500 focus:outline-none dark:border-slate-600 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
              placeholder="Add a concise title"
            />
            {titleError ? <p className="text-xs text-rose-600 dark:text-rose-300">{titleError}</p> : null}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="ticket-description" className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Description
            </label>
            <textarea
              id="ticket-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="min-h-[88px] w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-cyan-500 focus:outline-none dark:border-slate-600 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
              placeholder="Optional details"
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Tags</p>
            {tags.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">No tags yet. Create tags in Tag Manager.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => {
                  const selected = tagIds.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      className={`rounded-full border px-3 py-1 text-xs ${
                        selected
                          ? "border-cyan-300 bg-cyan-100 text-cyan-800 dark:border-cyan-400 dark:bg-cyan-500/20 dark:text-cyan-100"
                          : "border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                      }`}
                      onClick={() => toggleTag(tag.id)}
                    >
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              onClick={onClose}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-600 disabled:opacity-50 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : mode === "create" ? "Create Ticket" : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
