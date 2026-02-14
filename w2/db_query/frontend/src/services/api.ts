import type {
  DatabaseConnection,
  DatabaseDetailResponse,
  LlmHealthStatus,
  QueryExecutionRequest,
  QueryResult,
  SchemaMetadata,
  UpsertDatabaseRequest,
} from "../types/models";

const API_BASE = "/api/v1";

async function requestWithPath<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const contentType = response.headers.get("content-type") ?? "";

  if (!response.ok) {
    let details = "";
    if (contentType.includes("application/json")) {
      try {
        const payload = (await response.json()) as { detail?: unknown; message?: unknown };
        if (typeof payload.message === "string") {
          details = payload.message;
        } else if (typeof payload.detail === "string") {
          details = payload.detail;
        }
      } catch {
        details = "";
      }
    } else {
      try {
        const text = await response.text();
        if (text.trim().startsWith("<!doctype") || text.trim().startsWith("<html")) {
          details = "Received HTML response. Check Vite API proxy and backend server.";
        }
      } catch {
        details = "";
      }
    }

    throw new Error(details ? `Request failed: ${response.status} - ${details}` : `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.trim().startsWith("<!doctype") || text.trim().startsWith("<html")) {
      throw new Error("Invalid API response: received HTML instead of JSON. Check Vite proxy and backend server.");
    }
    throw new Error("Invalid API response: expected JSON payload");
  }

  return (await response.json()) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return requestWithPath<T>(`${API_BASE}${path}`, init);
}

async function requestRoot<T>(path: string, init?: RequestInit): Promise<T> {
  return requestWithPath<T>(path, init);
}

export const apiClient = {
  listDatabases: (): Promise<DatabaseConnection[]> => request<DatabaseConnection[]>("/dbs"),
  getDatabase: (name: string): Promise<DatabaseDetailResponse> =>
    request<DatabaseDetailResponse>(`/dbs/${name}`),
  upsertDatabase: (name: string, payload: { url: string }): Promise<DatabaseConnection> =>
    request<DatabaseConnection>(`/dbs/${name}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  refreshDatabase: (name: string): Promise<SchemaMetadata> =>
    request<SchemaMetadata>(`/dbs/${name}/refresh`, { method: "POST" }),
  deleteDatabase: (name: string): Promise<void> =>
    request<void>(`/dbs/${name}`, { method: "DELETE" }),
  executeQuery: (name: string, payload: QueryExecutionRequest): Promise<QueryResult> =>
    request<QueryResult>(`/dbs/${name}/query`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  generateSql: (
    name: string,
    payload: { prompt: string },
  ): Promise<{ generatedSql: string; context: Record<string, unknown> }> =>
    request<{ generatedSql: string; context: Record<string, unknown> }>(`/dbs/${name}/query/natural`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getLlmHealth: (): Promise<LlmHealthStatus> => requestRoot<LlmHealthStatus>("/health/llm"),
};

export type { UpsertDatabaseRequest };
