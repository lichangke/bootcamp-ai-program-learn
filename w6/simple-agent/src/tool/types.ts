import type { ExecutionContext } from "./context.ts";

export type JSONSchema = Record<string, unknown>;

export interface ToolResult {
  output: string;
  metadata?: Record<string, unknown>;
  error?: string;
}

export interface Tool {
  name: string;
  description: string;
  parameters: JSONSchema;
  execute: (args: unknown, context: ExecutionContext) => Promise<ToolResult> | ToolResult;
}

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: JSONSchema;
}
