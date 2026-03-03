import {
  Agent,
  InMemoryMCPTransport,
  MCPClient,
  ScriptedLLMClient,
  createMessage,
  textContent,
  toolCallContent,
} from "../src/index.ts";

const mcpTransport = new InMemoryMCPTransport({
  stock_quote: {
    description: "Get stock quote by symbol",
    inputSchema: {
      type: "object",
      properties: { symbol: { type: "string" } },
      required: ["symbol"],
      additionalProperties: false,
    },
    handler: async (args) => {
      const input = args as { symbol?: string };
      if (!input.symbol) {
        throw new Error("symbol is required");
      }
      return { symbol: input.symbol, price: 182.34, currency: "USD" };
    },
  },
});

const mcpClient = new MCPClient({ transport: mcpTransport });
await mcpClient.connect({
  name: "local-memory-mcp",
  transport: "stdio",
  command: "in-memory",
});

const mcpTools = await mcpClient.listTools();
const llm = new ScriptedLLMClient([
  {
    output: {
      content: [toolCallContent("stock_quote", { symbol: "AAPL" }, "mcp_call_1")],
      finishReason: "tool_calls",
      usage: { inputTokens: 21, outputTokens: 14 },
    },
  },
  {
    output: {
      content: [textContent("AAPL latest mocked price is 182.34 USD.")],
      finishReason: "stop",
      usage: { inputTokens: 31, outputTokens: 11 },
    },
  },
]);

const agent = new Agent(llm, {
  model: "mock-model",
  systemPrompt: "You are a market assistant.",
  tools: mcpTools,
});

const session = agent.createSession({
  messages: [createMessage("user", [textContent("What is AAPL price?")])],
});

await agent.run(session);
const final = session.messages.at(-1);
const text = final?.content.find((item) => item.type === "text");
console.log(text?.type === "text" ? text.text : "(no final text)");

await mcpClient.disconnect();
