export type TicketStatus = "open" | "done";

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface Ticket {
  id: number;
  title: string;
  description: string | null;
  status: TicketStatus;
  tag_ids: number[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface TicketListResponse {
  data: Ticket[];
  meta: {
    page: number;
    page_size: number;
    total: number;
  };
}

export interface TicketPayload {
  title: string;
  description: string | null;
  tag_ids: number[];
}

export interface Tag {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface TagPayload {
  name: string;
}
