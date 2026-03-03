# simple-agent SDK

`w6/simple-agent` 是一个基于 `specs/w6/0001-simple-agent-design.md` 的 TypeScript Agent SDK，覆盖多轮循环、工具调用、流式事件、权限控制、Doom Loop 检测、重试与 MCP 工具适配。

## 核心能力

- 多轮 Agent Loop：循环执行 `LLM -> tool calls -> tool results -> LLM`，直到结束。
- 统一 Tool 接口：可直接注册本地自定义工具。
- 流式处理：支持 `streamAgent` 逐事件输出。
- 权限系统：`allow / deny / ask` 规则。
- Doom Loop 检测：重复工具调用模式自动阻断。
- 消息压缩：上下文过长时可压缩历史消息。
- MCP 集成：`MCPClient + adaptMCPTool`，动态加载并调用 MCP 工具。
- 重试机制：指数退避重试封装。

## 目录结构

```text
src/
  agent/
  llm/
  tool/
  mcp/
  session/
  permission/
  utils/
examples/
tests/
```

## 安装与运行

```bash
cd w6/simple-agent
npm install
npm run test
```

示例：

```bash
npm run example:basic
npm run example:stream
npm run example:mcp
npm run example:live
npm run test:examples
```

## 快速开始

```ts
import {
  Agent,
  ScriptedLLMClient,
  createMessage,
  textContent,
  toolCallContent,
  type Tool,
} from "./src/index.ts";

const weatherTool: Tool = {
  name: "get_weather",
  description: "Get weather by city",
  parameters: {
    type: "object",
    properties: { location: { type: "string" } },
    required: ["location"],
  },
  async execute(args) {
    const { location } = args as { location: string };
    return { output: JSON.stringify({ location, temp: 22 }) };
  },
};

const llm = new ScriptedLLMClient([
  {
    output: {
      content: [toolCallContent("get_weather", { location: "Tokyo" }, "tc_1")],
      finishReason: "tool_calls",
      usage: { inputTokens: 10, outputTokens: 10 },
    },
  },
  {
    output: {
      content: [textContent("Tokyo is 22C.")],
      finishReason: "stop",
      usage: { inputTokens: 20, outputTokens: 10 },
    },
  },
]);

const agent = new Agent(llm, {
  model: "mock-model",
  systemPrompt: "You are helpful.",
  tools: [weatherTool],
});

const session = agent.createSession({
  messages: [createMessage("user", [textContent("Weather in Tokyo?")])],
});

await agent.run(session);
```

## MCP 使用方式

SDK 定义了统一 `MCPTransport` 协议，示例提供 `InMemoryMCPTransport`（便于本地开发与测试）。

```ts
import { MCPClient, InMemoryMCPTransport } from "./src/index.ts";

const transport = new InMemoryMCPTransport({
  stock_quote: {
    description: "Get stock quote",
    inputSchema: { type: "object", properties: { symbol: { type: "string" } }, required: ["symbol"] },
    handler: async (args) => ({ symbol: (args as { symbol: string }).symbol, price: 182.34 }),
  },
});

const mcp = new MCPClient({ transport });
await mcp.connect({ name: "local", transport: "stdio", command: "mock" });
const tools = await mcp.listTools();
```

在生产环境中，只需要实现一个符合 `MCPTransport` 接口的传输层即可对接真实 MCP Server（stdio/http/sse）。
