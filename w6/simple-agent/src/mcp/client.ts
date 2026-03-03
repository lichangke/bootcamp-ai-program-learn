import type { Tool, ToolResult } from "../tool/types.ts";
import { adaptMCPTool } from "./adapter.ts";
import type { MCPConfig, MCPToolDefinition, MCPTransport } from "./transport.ts";

export type MCPTransportResolver = (config: MCPConfig) => Promise<MCPTransport> | MCPTransport;

export interface MCPClientOptions {
  transport?: MCPTransport;
  transportResolver?: MCPTransportResolver;
}

export class MCPClient {
  private transport: MCPTransport | undefined;
  private currentConfig: MCPConfig | undefined;
  private readonly options: MCPClientOptions;

  constructor(options: MCPClientOptions = {}) {
    this.options = options;
    this.transport = options.transport;
  }

  async connect(config: MCPConfig): Promise<void> {
    this.currentConfig = config;
    if (!this.transport) {
      const resolver = this.options.transportResolver;
      if (!resolver) {
        throw new Error(
          "No MCP transport configured. Provide `transport` or `transportResolver` in MCPClient options.",
        );
      }
      this.transport = await resolver(config);
    }
    await this.transport.connect(config);
  }

  async disconnect(): Promise<void> {
    if (!this.transport) {
      return;
    }
    await this.transport.disconnect();
  }

  async listToolDefinitions(): Promise<MCPToolDefinition[]> {
    return this.getTransport().listTools();
  }

  async listTools(): Promise<Tool[]> {
    const definitions = await this.listToolDefinitions();
    return definitions.map((definition) => adaptMCPTool(this, definition));
  }

  async callTool(name: string, args: unknown): Promise<ToolResult> {
    const response = await this.getTransport().callTool(name, args);
    const output =
      typeof response.content === "string" ? response.content : JSON.stringify(response.content);
    return {
      output,
      ...(response.meta ? { metadata: response.meta } : {}),
      ...(response.isError ? { error: output } : {}),
    };
  }

  getConfig(): MCPConfig | undefined {
    return this.currentConfig;
  }

  private getTransport(): MCPTransport {
    if (this.transport) {
      return this.transport;
    }
    throw new Error("MCP client is not connected.");
  }
}
