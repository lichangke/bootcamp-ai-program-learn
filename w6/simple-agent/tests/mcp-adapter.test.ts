import { test } from "node:test";
import assert from "node:assert/strict";

import { InMemoryMCPTransport, MCPClient, adaptMCPTool } from "../src/index.ts";

test("adapted MCP tool can execute through MCP client", async () => {
  const transport = new InMemoryMCPTransport({
    ping: {
      description: "ping pong",
      inputSchema: { type: "object", additionalProperties: true },
      handler: async () => ({ pong: true }),
    },
  });

  const client = new MCPClient({ transport });
  await client.connect({
    name: "test-mcp",
    transport: "stdio",
    command: "mock",
  });

  const definitions = await client.listToolDefinitions();
  assert.equal(definitions.length, 1);
  const firstDefinition = definitions[0];
  assert.ok(firstDefinition, "expected at least one MCP tool definition");
  const tool = adaptMCPTool(client, firstDefinition);
  const result = await tool.execute({}, { sessionId: "s1", messageId: "m1" });

  assert.equal(result.error, undefined);
  assert.equal(result.output, "{\"pong\":true}");
  await client.disconnect();
});
