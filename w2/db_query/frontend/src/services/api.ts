import type {
  DatabaseConnection,
  DatabaseDetailResponse,
  QueryExecutionRequest,
  QueryResult,
} from "../types/models";

const API_BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
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
  refreshDatabase: (name: string): Promise<DatabaseDetailResponse> =>
    request<DatabaseDetailResponse>(`/dbs/${name}/refresh`, { method: "POST" }),
  executeQuery: (payload: QueryExecutionRequest): Promise<QueryResult> =>
    request<QueryResult>("/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

