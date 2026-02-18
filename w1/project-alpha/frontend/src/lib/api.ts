import type { ApiErrorPayload, Tag, TagPayload, Ticket, TicketListResponse, TicketPayload, TicketStatus } from "@/types/api";

const DEFAULT_API_BASE_URL = "http://localhost:8000/api";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_API_BASE_URL;

interface ListTicketParams {
  tagId?: number | null;
  q?: string | null;
  status?: TicketStatus | null;
  page: number;
  pageSize: number;
}

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;
  statusCode: number;

  constructor(message: string, options: { code: string; details: Record<string, unknown>; statusCode: number }) {
    super(message);
    this.code = options.code;
    this.details = options.details;
    this.statusCode = options.statusCode;
  }
}

function buildUrl(path: string, searchParams?: URLSearchParams): string {
  const prefix = API_BASE_URL.endsWith("/") ? API_BASE_URL.slice(0, -1) : API_BASE_URL;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  if (!searchParams || Array.from(searchParams.entries()).length === 0) {
    return `${prefix}${suffix}`;
  }
  return `${prefix}${suffix}?${searchParams.toString()}`;
}

async function request<T>(path: string, options: RequestInit = {}, searchParams?: URLSearchParams): Promise<T> {
  const response = await fetch(buildUrl(path, searchParams), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new ApiError(payload?.error?.message ?? "Request failed.", {
      code: payload?.error?.code ?? "HTTP_ERROR",
      details: payload?.error?.details ?? {},
      statusCode: response.status,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  async listTickets(params: ListTicketParams): Promise<TicketListResponse> {
    const searchParams = new URLSearchParams();
    if (params.tagId !== undefined && params.tagId !== null) {
      searchParams.set("tag_id", String(params.tagId));
    }
    if (params.q) {
      searchParams.set("q", params.q);
    }
    if (params.status) {
      searchParams.set("status", params.status);
    }
    searchParams.set("page", String(params.page));
    searchParams.set("page_size", String(params.pageSize));
    return request<TicketListResponse>("/tickets", { method: "GET" }, searchParams);
  },

  async getTicket(ticketId: number): Promise<Ticket> {
    const response = await request<{ data: Ticket }>(`/tickets/${ticketId}`, { method: "GET" });
    return response.data;
  },

  async createTicket(payload: TicketPayload): Promise<Ticket> {
    const response = await request<{ data: Ticket }>("/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return response.data;
  },

  async updateTicket(ticketId: number, payload: TicketPayload): Promise<Ticket> {
    const response = await request<{ data: Ticket }>(`/tickets/${ticketId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    return response.data;
  },

  async deleteTicket(ticketId: number): Promise<void> {
    await request<void>(`/tickets/${ticketId}`, {
      method: "DELETE",
    });
  },

  async completeTicket(ticketId: number): Promise<Ticket> {
    const response = await request<{ data: Ticket }>(`/tickets/${ticketId}/complete`, {
      method: "PATCH",
    });
    return response.data;
  },

  async reopenTicket(ticketId: number): Promise<Ticket> {
    const response = await request<{ data: Ticket }>(`/tickets/${ticketId}/reopen`, {
      method: "PATCH",
    });
    return response.data;
  },

  async listTags(): Promise<Tag[]> {
    const response = await request<{ data: Tag[] }>("/tags", { method: "GET" });
    return response.data;
  },

  async createTag(payload: TagPayload): Promise<Tag> {
    const response = await request<{ data: Tag }>("/tags", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return response.data;
  },

  async updateTag(tagId: number, payload: TagPayload): Promise<Tag> {
    const response = await request<{ data: Tag }>(`/tags/${tagId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    return response.data;
  },

  async deleteTag(tagId: number): Promise<void> {
    await request<void>(`/tags/${tagId}`, { method: "DELETE" });
  },
};
