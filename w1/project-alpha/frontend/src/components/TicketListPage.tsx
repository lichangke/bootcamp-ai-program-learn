import { useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Moon, Plus, Search, Settings2, Sun, Tags } from "lucide-react";

import { apiClient, ApiError } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { Ticket, TicketListResponse, TicketPayload, TicketStatus } from "@/types/api";

import { TagManagerDialog } from "./TagManagerDialog";
import { TicketEditorDialog } from "./TicketEditorDialog";
import { useToast } from "./ToastProvider";

interface QueryState {
  searchInput: string;
  selectedTagId: number | null;
  selectedStatus: TicketStatus | null;
  page: number;
  pageSize: number;
}

interface TicketListPageProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const TAG_COLOR_VARIANTS = [
  "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-400/50 dark:bg-sky-500/15 dark:text-sky-100",
  "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-400/50 dark:bg-emerald-500/15 dark:text-emerald-100",
  "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-400/50 dark:bg-amber-500/15 dark:text-amber-100",
  "border-fuchsia-300 bg-fuchsia-100 text-fuchsia-800 dark:border-fuchsia-400/50 dark:bg-fuchsia-500/15 dark:text-fuchsia-100",
  "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-400/50 dark:bg-rose-500/15 dark:text-rose-100",
  "border-lime-300 bg-lime-100 text-lime-800 dark:border-lime-400/50 dark:bg-lime-500/15 dark:text-lime-100",
  "border-cyan-300 bg-cyan-100 text-cyan-800 dark:border-cyan-400/50 dark:bg-cyan-500/15 dark:text-cyan-100",
  "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-400/50 dark:bg-orange-500/15 dark:text-orange-100",
  "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-400/50 dark:bg-indigo-500/15 dark:text-indigo-100",
  "border-teal-300 bg-teal-100 text-teal-800 dark:border-teal-400/50 dark:bg-teal-500/15 dark:text-teal-100",
] as const;

function hashText(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function getTagClass(tagName: string): string {
  const variant = TAG_COLOR_VARIANTS[hashText(tagName) % TAG_COLOR_VARIANTS.length];
  return `rounded-full border px-2 py-0.5 text-xs ${variant}`;
}

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error.";
}

export function TicketListPage({ theme, onToggleTheme }: TicketListPageProps) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  const [filters, setFilters] = useState<QueryState>({
    searchInput: "",
    selectedTagId: null,
    selectedStatus: null,
    page: 1,
    pageSize: 10,
  });
  const debouncedSearch = useDebouncedValue(filters.searchInput, 300);

  const [isTicketDialogOpen, setTicketDialogOpen] = useState(false);
  const [editingTicket, setEditingTicket] = useState<Ticket | null>(null);
  const [isTagDialogOpen, setTagDialogOpen] = useState(false);

  const tagsQuery = useQuery({
    queryKey: [queryKeys.tags],
    queryFn: apiClient.listTags,
  });

  const ticketsQuery = useQuery({
    queryKey: [
      queryKeys.tickets,
      {
        tagId: filters.selectedTagId,
        q: debouncedSearch,
        status: filters.selectedStatus,
        page: filters.page,
        pageSize: filters.pageSize,
      },
    ],
    queryFn: () =>
      apiClient.listTickets({
        tagId: filters.selectedTagId,
        q: debouncedSearch || null,
        status: filters.selectedStatus,
        page: filters.page,
        pageSize: filters.pageSize,
      }),
  });

  const invalidateTickets = async () => {
    await queryClient.invalidateQueries({ queryKey: [queryKeys.tickets] });
  };

  const invalidateTags = async () => {
    await queryClient.invalidateQueries({ queryKey: [queryKeys.tags] });
  };

  const createTicketMutation = useMutation({
    mutationFn: (payload: TicketPayload) => apiClient.createTicket(payload),
    onSuccess: async () => {
      pushToast("Ticket created.", "success");
      await invalidateTickets();
      setTicketDialogOpen(false);
      setEditingTicket(null);
    },
    onError: (error) => pushToast(toErrorMessage(error), "error"),
  });

  const updateTicketMutation = useMutation({
    mutationFn: ({ ticketId, payload }: { ticketId: number; payload: TicketPayload }) =>
      apiClient.updateTicket(ticketId, payload),
    onSuccess: async () => {
      pushToast("Ticket updated.", "success");
      await invalidateTickets();
      setTicketDialogOpen(false);
      setEditingTicket(null);
    },
    onError: (error) => pushToast(toErrorMessage(error), "error"),
  });

  const deleteTicketMutation = useMutation({
    mutationFn: (ticketId: number) => apiClient.deleteTicket(ticketId),
    onMutate: async (ticketId) => {
      await queryClient.cancelQueries({ queryKey: [queryKeys.tickets] });
      const snapshots = queryClient.getQueriesData<TicketListResponse>({ queryKey: [queryKeys.tickets] });
      snapshots.forEach(([key, value]) => {
        if (!value) {
          return;
        }
        queryClient.setQueryData<TicketListResponse>(key, {
          ...value,
          data: value.data.filter((ticket) => ticket.id !== ticketId),
          meta: { ...value.meta, total: Math.max(0, value.meta.total - 1) },
        });
      });
      return { snapshots };
    },
    onError: (error, _, context) => {
      context?.snapshots?.forEach(([key, value]) => queryClient.setQueryData(key, value));
      pushToast(toErrorMessage(error), "error");
    },
    onSuccess: () => pushToast("Ticket deleted.", "success"),
    onSettled: async () => {
      await invalidateTickets();
    },
  });

  const toggleTicketMutation = useMutation({
    mutationFn: ({ ticketId, nextStatus }: { ticketId: number; nextStatus: TicketStatus }) =>
      nextStatus === "done" ? apiClient.completeTicket(ticketId) : apiClient.reopenTicket(ticketId),
    onMutate: async ({ ticketId, nextStatus }) => {
      await queryClient.cancelQueries({ queryKey: [queryKeys.tickets] });
      const snapshots = queryClient.getQueriesData<TicketListResponse>({ queryKey: [queryKeys.tickets] });
      snapshots.forEach(([key, value]) => {
        if (!value) {
          return;
        }
        queryClient.setQueryData<TicketListResponse>(key, {
          ...value,
          data: value.data.map((ticket) => {
            if (ticket.id !== ticketId) {
              return ticket;
            }
            return {
              ...ticket,
              status: nextStatus,
              completed_at: nextStatus === "done" ? new Date().toISOString() : null,
            };
          }),
        });
      });
      return { snapshots };
    },
    onError: (error, _, context) => {
      context?.snapshots?.forEach(([key, value]) => queryClient.setQueryData(key, value));
      pushToast(toErrorMessage(error), "error");
    },
    onSuccess: (_, variables) =>
      pushToast(variables.nextStatus === "done" ? "Ticket completed." : "Ticket reopened.", "success"),
    onSettled: async () => {
      await invalidateTickets();
    },
  });

  const createTagMutation = useMutation({
    mutationFn: (name: string) => apiClient.createTag({ name }),
    onSuccess: async () => {
      pushToast("Tag created.", "success");
      await invalidateTags();
    },
    onError: (error) => pushToast(toErrorMessage(error), "error"),
  });

  const updateTagMutation = useMutation({
    mutationFn: ({ tagId, name }: { tagId: number; name: string }) => apiClient.updateTag(tagId, { name }),
    onSuccess: async () => {
      pushToast("Tag updated.", "success");
      await Promise.all([invalidateTags(), invalidateTickets()]);
    },
    onError: (error) => pushToast(toErrorMessage(error), "error"),
  });

  const deleteTagMutation = useMutation({
    mutationFn: (tagId: number) => apiClient.deleteTag(tagId),
    onSuccess: async () => {
      pushToast("Tag deleted.", "success");
      await Promise.all([invalidateTags(), invalidateTickets()]);
    },
    onError: (error) => pushToast(toErrorMessage(error), "error"),
  });

  const tickets = ticketsQuery.data?.data ?? [];
  const meta = ticketsQuery.data?.meta;
  const totalPages = meta ? Math.max(1, Math.ceil(meta.total / meta.page_size)) : 1;

  const hasFilter = Boolean(debouncedSearch || filters.selectedTagId !== null || filters.selectedStatus !== null);
  const emptyMessage = hasFilter ? "No matching tickets for current filters." : "No tickets yet. Create one.";

  const tagNameById = useMemo(() => {
    const map = new Map<number, string>();
    (tagsQuery.data ?? []).forEach((tag) => map.set(tag.id, tag.name));
    return map;
  }, [tagsQuery.data]);

  const submitTicket = async (payload: TicketPayload) => {
    if (editingTicket) {
      await updateTicketMutation.mutateAsync({ ticketId: editingTicket.id, payload });
      return;
    }
    await createTicketMutation.mutateAsync(payload);
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6">
        <header className="rounded-xl border border-slate-200 bg-gradient-to-r from-white to-slate-100 p-5 shadow-sm dark:border-slate-800 dark:from-slate-900 dark:to-slate-800 dark:shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">Project Alpha</p>
              <h1 className="mt-1 text-2xl font-semibold">Ticket Board</h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800"
                onClick={onToggleTheme}
              >
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800"
                onClick={() => setTagDialogOpen(true)}
              >
                <Tags className="h-4 w-4" />
                Tag Manager
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-md bg-cyan-500 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-600 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
                onClick={() => {
                  setEditingTicket(null);
                  setTicketDialogOpen(true);
                }}
              >
                <Plus className="h-4 w-4" />
                New Ticket
              </button>
            </div>
          </div>
        </header>

        <section className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr,auto,auto,auto] dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-none">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 dark:text-slate-400" />
            <input
              value={filters.searchInput}
              onChange={(event) => setFilters((prev) => ({ ...prev, page: 1, searchInput: event.target.value }))}
              className="w-full rounded-md border border-slate-300 bg-white px-9 py-2 text-sm text-slate-900 focus:border-cyan-500 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
              placeholder="Search by ticket title"
            />
          </label>

          <select
            value={filters.selectedTagId ?? ""}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                page: 1,
                selectedTagId: event.target.value ? Number(event.target.value) : null,
              }))
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="">All tags</option>
            {(tagsQuery.data ?? []).map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </select>

          <select
            value={filters.selectedStatus ?? ""}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                page: 1,
                selectedStatus: event.target.value ? (event.target.value as TicketStatus) : null,
              }))
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="">All status</option>
            <option value="open">Open</option>
            <option value="done">Done</option>
          </select>

          <button
            type="button"
            className="inline-flex items-center justify-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                searchInput: "",
                selectedTagId: null,
                selectedStatus: null,
                page: 1,
              }))
            }
          >
            <Settings2 className="h-4 w-4" />
            Reset
          </button>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-none">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
            <div className="inline-flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <ListChecks className="h-4 w-4" />
              Tickets
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {meta ? `${meta.total} total` : "--"}
            </div>
          </div>

          {ticketsQuery.isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2].map((id) => (
                <div key={id} className="h-16 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800/70" />
              ))}
            </div>
          ) : null}

          {ticketsQuery.isError ? (
            <div className="p-4 text-sm text-rose-600 dark:text-rose-300">
              Failed to load tickets: {toErrorMessage(ticketsQuery.error)}
            </div>
          ) : null}

          {!ticketsQuery.isLoading && !ticketsQuery.isError && tickets.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-500 dark:text-slate-400">{emptyMessage}</div>
          ) : null}

          {!ticketsQuery.isLoading && !ticketsQuery.isError && tickets.length > 0 ? (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {tickets.map((ticket) => (
                <article key={ticket.id} className="space-y-2 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-base font-medium text-slate-900 dark:text-slate-100">{ticket.title}</h3>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        ticket.status === "done"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-100"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-100"
                      }`}
                    >
                      {ticket.status}
                    </span>
                  </div>
                  {ticket.description ? (
                    <p className="text-sm text-slate-600 dark:text-slate-300">{ticket.description}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-1">
                    {ticket.tag_ids.map((tagId) => {
                      const tagLabel = tagNameById.get(tagId) ?? `Tag#${tagId}`;
                      return (
                        <span key={tagId} className={getTagClass(tagLabel)}>
                          {tagLabel}
                        </span>
                      );
                    })}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-2 py-1 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800"
                      onClick={() => {
                        setEditingTicket(ticket);
                        setTicketDialogOpen(true);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="rounded border border-rose-300 px-2 py-1 text-rose-700 hover:bg-rose-100 disabled:opacity-50 dark:border-rose-500/70 dark:text-rose-200 dark:hover:bg-rose-500/10"
                      onClick={() => {
                        if (window.confirm(`Delete ticket '${ticket.title}'?`)) {
                          void deleteTicketMutation.mutateAsync(ticket.id);
                        }
                      }}
                      disabled={deleteTicketMutation.isPending}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      className="rounded border border-cyan-300 px-2 py-1 text-cyan-700 hover:bg-cyan-100 disabled:opacity-50 dark:border-cyan-500/70 dark:text-cyan-100 dark:hover:bg-cyan-500/10"
                      onClick={() =>
                        void toggleTicketMutation.mutateAsync({
                          ticketId: ticket.id,
                          nextStatus: ticket.status === "open" ? "done" : "open",
                        })
                      }
                      disabled={toggleTicketMutation.isPending}
                    >
                      {ticket.status === "open" ? "Complete" : "Reopen"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-none">
          <div className="text-sm text-slate-700 dark:text-slate-300">
            Page {filters.page} / {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800"
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page - 1 }))}
              disabled={filters.page <= 1 || ticketsQuery.isLoading}
            >
              Prev
            </button>
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800"
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
              disabled={filters.page >= totalPages || ticketsQuery.isLoading}
            >
              Next
            </button>
          </div>
        </footer>
      </div>

      <TicketEditorDialog
        open={isTicketDialogOpen}
        mode={editingTicket ? "edit" : "create"}
        tags={tagsQuery.data ?? []}
        initialValue={
          editingTicket
            ? {
                title: editingTicket.title,
                description: editingTicket.description,
                tagIds: editingTicket.tag_ids,
              }
            : null
        }
        isSaving={createTicketMutation.isPending || updateTicketMutation.isPending}
        onClose={() => {
          setTicketDialogOpen(false);
          setEditingTicket(null);
        }}
        onSubmit={submitTicket}
      />

      <TagManagerDialog
        open={isTagDialogOpen}
        tags={tagsQuery.data ?? []}
        isLoading={tagsQuery.isLoading}
        isCreating={createTagMutation.isPending}
        isUpdating={updateTagMutation.isPending}
        isDeleting={deleteTagMutation.isPending}
        onClose={() => setTagDialogOpen(false)}
        onCreate={async (name) => {
          await createTagMutation.mutateAsync(name);
        }}
        onUpdate={async (tagId, name) => {
          await updateTagMutation.mutateAsync({ tagId, name });
        }}
        onDelete={async (tagId) => {
          await deleteTagMutation.mutateAsync(tagId);
        }}
      />
    </main>
  );
}
