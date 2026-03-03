import { test } from "node:test";
import assert from "node:assert/strict";

import {
  Agent,
  ScriptedLLMClient,
  createMessage,
  textContent,
  toolCallContent,
  type Tool,
} from "../src/index.ts";

test("runAgent executes tool calls and finishes with assistant response", async () => {
  let called = 0;
  const tools: Tool[] = [
    {
      name: "sum",
      description: "sum two numbers",
      parameters: {
        type: "object",
        properties: { a: { type: "number" }, b: { type: "number" } },
        required: ["a", "b"],
        additionalProperties: false,
      },
      async execute(args) {
        called += 1;
        const input = args as { a: number; b: number };
        return { output: String(input.a + input.b) };
      },
    },
  ];

  const llm = new ScriptedLLMClient([
    {
      output: {
        content: [toolCallContent("sum", { a: 1, b: 2 }, "tc_1")],
        finishReason: "tool_calls",
        usage: { inputTokens: 10, outputTokens: 6 },
      },
    },
    {
      output: {
        content: [textContent("The result is 3.")],
        finishReason: "stop",
        usage: { inputTokens: 14, outputTokens: 9 },
      },
    },
  ]);

  const agent = new Agent(llm, {
    model: "mock-model",
    systemPrompt: "You are a calculator.",
    tools,
  });

  const session = agent.createSession({
    messages: [createMessage("user", [textContent("compute 1 + 2")])],
  });

  await agent.run(session);

  assert.equal(called, 1);
  assert.equal(session.status, "completed");
  assert.equal(session.messages.length, 4);
  const toolMessage = session.messages[2];
  assert.ok(toolMessage, "expected tool message at index 2");
  assert.equal(toolMessage.role, "tool");
  const resultBlock = toolMessage.content[0];
  assert.ok(resultBlock, "expected tool result block at index 0");
  assert.equal(resultBlock.type, "tool_result");
  if (resultBlock.type !== "tool_result") {
    throw new Error("expected tool_result block");
  }
  assert.equal(resultBlock.result, "3");
});
