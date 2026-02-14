export type ErrorType = "connection" | "syntax" | "validation" | "execution" | "timeout";

export interface QueryError {
  errorType: ErrorType;
  errorCode: string;
  message: string;
  details?: string | null;
  query?: string | null;
}

export interface DatabaseConnection {
  name: string;
  url: string;
  createdAt: string;
  updatedAt: string;
  status: "active" | "error" | "unknown";
}

export interface ColumnMetadata {
  columnName: string;
  dataType: string;
  isNullable: boolean;
  defaultValue?: string | null;
  maxLength?: number | null;
  numericPrecision?: number | null;
}

export interface TableMetadata {
  schemaName: string;
  tableName: string;
  tableType: "TABLE" | "VIEW";
  columns: ColumnMetadata[];
  primaryKeys: string[];
}

export interface SchemaMetadata {
  connectionName: string;
  databaseName: string;
  fetchedAt: string;
  tables: TableMetadata[];
  views: TableMetadata[];
}

export interface DatabaseDetailResponse {
  connection: DatabaseConnection;
  metadata: SchemaMetadata;
}

export interface UpsertDatabaseRequest {
  url: string;
}

export interface ColumnDefinition {
  name: string;
  type: string;
}

export interface QueryResult {
  columns: ColumnDefinition[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionTime: number;
  query: string;
}

export interface QueryExecutionRequest {
  sql: string;
}

export interface LlmHealthStatus {
  provider: string;
  model: string;
  baseUrl: string;
  status: string;
  reachable: boolean;
  latencyMs?: number;
  response?: string;
  details?: string;
}
