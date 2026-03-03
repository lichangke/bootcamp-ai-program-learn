# Design Spec Compliance Checklist

Spec source: `specs/w6/0001-simple-agent-design.md`

## 1-3. Core model and loop

- Message structure (`Message`, `MessageContent`, text/tool_call/tool_result): implemented in `src/session/message.ts`.
- Tool model (`Tool`, `ToolResult`, JSON schema params): implemented in `src/tool/types.ts`.
- Session model (`Session`, `status`, `systemPrompt`, `model`, `tools`): implemented in `src/session/session.ts`.
- Tool registry (`register/unregister/get/list/toToolDefinitions`): implemented in `src/tool/registry.ts`.
- Tool executor (`ToolExecutor.execute` with not-found/error handling): implemented in `src/tool/executor.ts`.
- Agent loop (`runAgent`) with multi-step tool-call cycle and max steps: implemented in `src/agent/loop.ts`.

## 3.1 + 6.1 LLM and streaming

- LLM input/output/event contracts: `src/llm/client.ts`.
- Stream bridge helpers: `src/llm/stream.ts`.
- Streaming agent loop (`streamAgent`): `src/agent/loop.ts`.

## 4. MCP integration

- MCP client (`connect/disconnect/listTools/callTool`): `src/mcp/client.ts`.
- MCP tool adapter (`adaptMCPTool`): `src/mcp/adapter.ts`.
- MCP transport abstraction + in-memory demo transport: `src/mcp/transport.ts`.

## 5. Permission system

- Permission model (`allow/deny/ask`) and matching logic: `src/permission/manager.ts`.
- Permission check before tool execution: integrated in `src/tool/executor.ts`.

## 7. Retry

- Exponential backoff retry utility: `src/utils/retry.ts`.
- Integrated into `runAgent` LLM call path: `src/agent/loop.ts`.

## 9. Design principles support

- Tool-first architecture: `ToolRegistry`, `ToolExecutor`, adapter APIs.
- Loop-until-complete behavior: `runAgent`, `streamAgent`.
- Doom loop detection: `src/utils/doom-loop.ts` used by both loops.
- Message compression (optional): `src/utils/message-compressor.ts` and loop integration.

## 8. Examples

- Custom tool usage: `examples/basic-custom-tools.ts`.
- Streaming usage: `examples/streaming.ts`.
- MCP usage (with dynamic MCP tool loading path): `examples/mcp-tools.ts`.

## Validation

- Tests:
  - `tests/agent-loop.test.ts`
  - `tests/permission.test.ts`
  - `tests/mcp-adapter.test.ts`
- Verified command:
  - `npm run test`
