import { test } from "node:test";
import assert from "node:assert/strict";

import {
  PermissionManager,
  ToolExecutor,
  ToolRegistry,
  createSession,
  toolCallContent,
  type Tool,
} from "../src/index.ts";

test("permission manager deny rule blocks tool execution", async () => {
  let calls = 0;
  const tool: Tool = {
    name: "delete_file",
    description: "delete a file",
    parameters: { type: "object" },
    async execute() {
      calls += 1;
      return { output: "deleted" };
    },
  };

  const registry = new ToolRegistry();
  registry.register(tool);
  const permissions = new PermissionManager([{ tool: "delete_*", action: "deny" }]);
  const executor = new ToolExecutor(registry, permissions);
  const session = createSession({
    model: { name: "mock-model" },
    systemPrompt: "test",
  });

  const result = await executor.execute(
    toolCallContent("delete_file", { path: "/tmp/a.txt" }, "tc_1"),
    { sessionId: session.id, messageId: "assistant_1" },
    session,
  );

  assert.equal(result.isError, true);
  assert.match(result.result, /Permission denied/);
  assert.equal(calls, 0);
});

test("permission ask rule can allow tool execution", async () => {
  let calls = 0;
  const tool: Tool = {
    name: "read_secret",
    description: "reads secret",
    parameters: { type: "object" },
    async execute() {
      calls += 1;
      return { output: "ok" };
    },
  };

  const registry = new ToolRegistry();
  registry.register(tool);
  const permissions = new PermissionManager(
    [{ tool: "read_secret", action: "ask" }],
    async () => "allow",
  );
  const executor = new ToolExecutor(registry, permissions);
  const session = createSession({
    model: { name: "mock-model" },
    systemPrompt: "test",
  });

  const result = await executor.execute(
    toolCallContent("read_secret", {}, "tc_2"),
    { sessionId: session.id, messageId: "assistant_2" },
    session,
  );

  assert.equal(result.isError, undefined);
  assert.equal(result.result, "ok");
  assert.equal(calls, 1);
});
