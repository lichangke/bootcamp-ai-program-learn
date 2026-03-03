import type { JSONSchema } from "../tool/types.ts";

export interface MCPConfig {
  name: string;
  transport: "stdio" | "http" | "sse";
  command?: string;
  args?: string[];
  url?: string;
}

export interface MCPToolDefinition {
  name: string;
  description: string;
  inputSchema: JSONSchema;
}

export interface MCPToolCallResponse {
  content: unknown;
  meta?: Record<string, unknown>;
  isError?: boolean;
}

export interface MCPTransport {
  connect(config: MCPConfig): Promise<void>;
  disconnect(): Promise<void>;
  listTools(): Promise<MCPToolDefinition[]>;
  callTool(name: string, args: unknown): Promise<MCPToolCallResponse>;
}

export interface InMemoryMCPTool {
  description: string;
  inputSchema: JSONSchema;
  handler: (args: unknown) => Promise<unknown> | unknown;
}

export class InMemoryMCPTransport implements MCPTransport {
  private connected = false;
  private readonly tools: Record<string, InMemoryMCPTool>;

  constructor(tools: Record<string, InMemoryMCPTool>) {
    this.tools = tools;
  }

  async connect(_config: MCPConfig): Promise<void> {
    this.connected = true;
  }

  async disconnect(): Promise<void> {
    this.connected = false;
  }

  async listTools(): Promise<MCPToolDefinition[]> {
    this.assertConnected();
    return Object.entries(this.tools).map(([name, value]) => ({
      name,
      description: value.description,
      inputSchema: value.inputSchema,
    }));
  }

  async callTool(name: string, args: unknown): Promise<MCPToolCallResponse> {
    this.assertConnected();
    const tool = this.tools[name];
    if (!tool) {
      return { content: `MCP tool not found: ${name}`, isError: true };
    }
    try {
      const content = await tool.handler(args);
      return { content };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: message, isError: true };
    }
  }

  private assertConnected(): void {
    if (!this.connected) {
      throw new Error("MCP transport is not connected.");
    }
  }
}
