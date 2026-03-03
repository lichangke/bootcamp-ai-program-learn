import {
  Agent,
  ScriptedLLMClient,
  createMessage,
  textContent,
  type Tool,
} from "../src/index.ts";

const calculatorTool: Tool = {
  name: "calculator",
  description: "Add two numbers",
  parameters: {
    type: "object",
    properties: {
      a: { type: "number" },
      b: { type: "number" },
    },
    required: ["a", "b"],
    additionalProperties: false,
  },
  async execute(args) {
    const input = args as { a?: number; b?: number };
    if (typeof input.a !== "number" || typeof input.b !== "number") {
      return { output: "Invalid arguments", error: "INVALID_ARGS" };
    }
    return { output: String(input.a + input.b) };
  },
};

const llm = new ScriptedLLMClient([
  {
    streamEvents: [
      { type: "text_delta", text: "I will calculate that now. " },
      { type: "tool_call_start", id: "tc_1", name: "calculator" },
      { type: "tool_call_delta", id: "tc_1", arguments: "{\"a\":7,\"b\":5}" },
      { type: "tool_call_end", id: "tc_1" },
      { type: "finish", reason: "tool_calls", usage: { inputTokens: 20, outputTokens: 15 } },
    ],
  },
  {
    streamEvents: [
      { type: "text_delta", text: "The result is 12." },
      { type: "finish", reason: "stop", usage: { inputTokens: 28, outputTokens: 8 } },
    ],
  },
]);

const agent = new Agent(llm, {
  model: "mock-model",
  systemPrompt: "You are a math assistant.",
  tools: [calculatorTool],
});

const session = agent.createSession({
  messages: [createMessage("user", [textContent("What is 7 + 5?")])],
});

for await (const event of agent.stream(session)) {
  switch (event.type) {
    case "text":
      process.stdout.write(event.text);
      break;
    case "tool_call":
      console.log(`\n[tool_call] ${event.name} ${JSON.stringify(event.args)}`);
      break;
    case "tool_result":
      console.log(`[tool_result] ${event.name}: ${event.result}`);
      break;
    case "message_end":
      console.log(`\n[message_end] reason=${event.finishReason}`);
      break;
    case "error":
      console.error(`[error] ${event.error.message}`);
      break;
    default:
      break;
  }
}
