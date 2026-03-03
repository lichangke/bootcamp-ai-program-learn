import type { Tool, ToolDefinition } from "./types.ts";

export class ToolRegistry {
  private readonly tools = new Map<string, Tool>();

  register(tool: Tool): void {
    if (this.tools.has(tool.name)) {
      throw new Error(`Tool already registered: ${tool.name}`);
    }
    this.tools.set(tool.name, tool);
  }

  registerMany(tools: Tool[]): void {
    for (const tool of tools) {
      this.register(tool);
    }
  }

  unregister(name: string): void {
    this.tools.delete(name);
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  list(): Tool[] {
    return [...this.tools.values()];
  }

  toToolDefinitions(): ToolDefinition[] {
    return this.list().map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.parameters,
    }));
  }
}
