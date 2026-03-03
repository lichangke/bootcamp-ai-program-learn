import {
  Agent,
  ScriptedLLMClient,
  createMessage,
  textContent,
  toolCallContent,
  type Tool,
} from "../src/index.ts";

const getWeatherTool: Tool = {
  name: "get_weather",
  description: "Get weather by city name",
  parameters: {
    type: "object",
    properties: {
      location: { type: "string" },
    },
    required: ["location"],
    additionalProperties: false,
  },
  async execute(args) {
    const input = args as { location?: string };
    if (!input.location) {
      return { output: "Missing location", error: "INVALID_ARGS" };
    }
    return { output: JSON.stringify({ location: input.location, temp: 22, condition: "sunny" }) };
  },
};

const llm = new ScriptedLLMClient([
  {
    output: {
      content: [toolCallContent("get_weather", { location: "Tokyo" }, "call_1")],
      finishReason: "tool_calls",
      usage: { inputTokens: 25, outputTokens: 12 },
    },
  },
  {
    output: {
      content: [textContent("Tokyo is sunny and around 22C.")],
      finishReason: "stop",
      usage: { inputTokens: 35, outputTokens: 18 },
    },
  },
]);

const agent = new Agent(llm, {
  model: "mock-model",
  systemPrompt: "You are a concise weather assistant.",
  tools: [getWeatherTool],
});

const session = agent.createSession({
  messages: [createMessage("user", [textContent("What is the weather in Tokyo?")])],
});

await agent.run(session);
const finalMessage = session.messages.at(-1);
const finalText = finalMessage?.content.find((item) => item.type === "text");
console.log(finalText?.type === "text" ? finalText.text : "(no final text)");
