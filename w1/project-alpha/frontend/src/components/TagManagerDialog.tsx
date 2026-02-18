import { useState } from "react";

import type { Tag } from "@/types/api";

interface TagManagerDialogProps {
  open: boolean;
  tags: Tag[];
  isLoading: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void> | void;
  onUpdate: (tagId: number, name: string) => Promise<void> | void;
  onDelete: (tagId: number) => Promise<void> | void;
}

export function TagManagerDialog({
  open,
  tags,
  isLoading,
  isCreating,
  isUpdating,
  isDeleting,
  onClose,
  onCreate,
  onUpdate,
  onDelete,
}: TagManagerDialogProps) {
  const [newTagName, setNewTagName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");

  if (!open) {
    return null;
  }

  const submitCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = newTagName.trim();
    if (!normalized) {
      return;
    }
    await onCreate(normalized);
    setNewTagName("");
  };

  const startEdit = (tag: Tag) => {
    setEditingId(tag.id);
    setEditingName(tag.name);
  };

  const submitEdit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editingId === null) {
      return;
    }
    const normalized = editingName.trim();
    if (!normalized) {
      return;
    }
    await onUpdate(editingId, normalized);
    setEditingId(null);
    setEditingName("");
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-xl rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100">Tag Manager</h2>
          <button
            type="button"
            className="rounded border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <form className="mb-4 flex gap-2" onSubmit={submitCreate}>
          <input
            value={newTagName}
            onChange={(event) => setNewTagName(event.target.value)}
            className="flex-1 rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:border-cyan-300 focus:outline-none"
            placeholder="New tag name"
          />
          <button
            type="submit"
            className="rounded-md bg-cyan-400 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-300 disabled:opacity-50"
            disabled={isCreating}
          >
            {isCreating ? "Adding..." : "Add Tag"}
          </button>
        </form>

        <div className="max-h-80 space-y-2 overflow-auto pr-1">
          {isLoading ? <p className="text-sm text-slate-300">Loading tags...</p> : null}
          {!isLoading && tags.length === 0 ? <p className="text-sm text-slate-400">No tags created yet.</p> : null}
          {tags.map((tag) => (
            <div
              key={tag.id}
              className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2"
            >
              {editingId === tag.id ? (
                <form className="flex flex-1 gap-2" onSubmit={submitEdit}>
                  <input
                    value={editingName}
                    onChange={(event) => setEditingName(event.target.value)}
                    className="flex-1 rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-slate-50"
                  />
                  <button
                    type="submit"
                    className="rounded border border-cyan-400 px-2 py-1 text-xs text-cyan-100 disabled:opacity-50"
                    disabled={isUpdating}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200"
                    onClick={() => setEditingId(null)}
                  >
                    Cancel
                  </button>
                </form>
              ) : (
                <>
                  <span className="text-sm text-slate-100">{tag.name}</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
                      onClick={() => startEdit(tag)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="rounded border border-rose-500/70 px-2 py-1 text-xs text-rose-200 hover:bg-rose-500/10 disabled:opacity-50"
                      onClick={() => {
                        if (window.confirm(`Delete tag '${tag.name}'? This also clears relations.`)) {
                          void onDelete(tag.id);
                        }
                      }}
                      disabled={isDeleting}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
