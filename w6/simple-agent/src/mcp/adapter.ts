import type { MCPClient } from "./client.ts";
import type { MCPToolDefinition } from "./transport.ts";
import type { Tool } from "../tool/types.ts";
import type { ToolRegistry } from "../tool/registry.ts";

export function adaptMCPTool(client: MCPClient, mcpTool: MCPToolDefinition): Tool {
  return {
    name: mcpTool.name,
    description: mcpTool.description,
    parameters: mcpTool.inputSchema,
    execute: async (args) => client.callTool(mcpTool.name, args),
  };
}

export async function loadMCPTools(client: MCPClient): Promise<Tool[]> {
  const definitions = await client.listToolDefinitions();
  return definitions.map((definition) => adaptMCPTool(client, definition));
}

export async function registerMCPTools(client: MCPClient, registry: ToolRegistry): Promise<Tool[]> {
  const tools = await loadMCPTools(client);
  registry.registerMany(tools);
  return tools;
}
