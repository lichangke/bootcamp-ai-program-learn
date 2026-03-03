import type { LLMOutput } from "../llm/client.ts";
import type { AgentEvent, AgentRunConfig } from "./agent.ts";
import type { Message, ToolCallContent, ToolResultContent } from "../session/message.ts";
import {
  createMessage,
  isToolCallContent,
  mergeAdjacentTextContent,
  textContent,
  toolCallContent,
} from "../session/message.ts";
import type { Session } from "../session/session.ts";
import { ToolExecutor } from "../tool/executor.ts";
import { ToolRegistry } from "../tool/registry.ts";
import { DoomLoopDetector } from "../utils/doom-loop.ts";
import { DEFAULT_RETRY_CONFIG, withRetry } from "../utils/retry.ts";

export async function runAgent(
  session: Session,
  config: AgentRunConfig,
  abortSignal?: AbortSignal,
): Promise<Message[]> {
  const registry = buildToolRegistry(session, config);
  const executor = new ToolExecutor(registry, config.permissionManager);
  const doomLoopDetector = new DoomLoopDetector(config.doomLoopMaxRepeats ?? 3);
  const maxSteps = config.maxSteps ?? 200;

  session.status = "running";
  try {
    for (let step = 0; step < maxSteps; step += 1) {
      assertNotAborted(abortSignal);
      config.onEvent?.({ type: "message_start", role: "assistant" });

      if (
        config.messageCompressor &&
        session.messages.length > (config.compressionTriggerMessages ?? 32)
      ) {
        session.messages = await config.messageCompressor.compress(session.messages);
      }

      const response = await withRetry(
        async () =>
          config.llmClient.generate({
            model: config.model,
            messages: session.messages,
            systemPrompt: config.systemPrompt,
            tools: registry.toToolDefinitions(),
            ...(abortSignal ? { abortSignal } : {}),
          }),
        config.retryConfig ?? DEFAULT_RETRY_CONFIG,
      );

      const assistantMessage = createMessage("assistant", mergeAdjacentTextContent(response.content));
      session.messages.push(assistantMessage);
      emitTextEvents(response, config.onEvent);
      config.onEvent?.({ type: "message_end", finishReason: response.finishReason });

      const toolCalls = assistantMessage.content.filter(isToolCallContent);
      if (toolCalls.length === 0) {
        session.status = "completed";
        return session.messages;
      }

      doomLoopDetector.record(toolCalls);
      const callNameById = new Map(toolCalls.map((call) => [call.id, call.name]));
      for (const call of toolCalls) {
        config.onEvent?.({ type: "tool_call", name: call.name, args: call.arguments });
      }

      const results = await Promise.all(
        toolCalls.map((call) =>
          executor.execute(
            call,
            {
              sessionId: session.id,
              messageId: assistantMessage.id,
              ...(abortSignal ? { abortSignal } : {}),
            },
            session,
          ),
        ),
      );

      for (const result of results) {
        const toolResultEvent =
          result.isError === undefined
            ? {
                type: "tool_result" as const,
                name: callNameById.get(result.toolCallId) ?? "unknown_tool",
                result: result.result,
              }
            : {
                type: "tool_result" as const,
                name: callNameById.get(result.toolCallId) ?? "unknown_tool",
                result: result.result,
                isError: result.isError,
              };
        config.onEvent?.(toolResultEvent);
      }

      session.messages.push(createMessage("tool", results));
    }
  } catch (error) {
    const normalized = error instanceof Error ? error : new Error(String(error));
    session.status = "error";
    config.onEvent?.({ type: "error", error: normalized });
    throw normalized;
  }

  session.status = "error";
  const maxStepError = new Error(`Agent exceeded maxSteps=${maxSteps}`);
  config.onEvent?.({ type: "error", error: maxStepError });
  throw maxStepError;
}

export async function* streamAgent(
  session: Session,
  config: AgentRunConfig,
  abortSignal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const registry = buildToolRegistry(session, config);
  const executor = new ToolExecutor(registry, config.permissionManager);
  const doomLoopDetector = new DoomLoopDetector(config.doomLoopMaxRepeats ?? 3);
  const maxSteps = config.maxSteps ?? 200;

  session.status = "running";
  try {
    for (let step = 0; step < maxSteps; step += 1) {
      assertNotAborted(abortSignal);
      if (
        config.messageCompressor &&
        session.messages.length > (config.compressionTriggerMessages ?? 32)
      ) {
        session.messages = await config.messageCompressor.compress(session.messages);
      }

      const startEvent: AgentEvent = { type: "message_start", role: "assistant" };
      config.onEvent?.(startEvent);
      yield startEvent;

      const content: Message["content"] = [];
      const toolCalls: ToolCallContent[] = [];
      const partialCalls = new Map<string, { id: string; name: string; argsText: string }>();
      let finishReason = "stop";

      for await (const event of config.llmClient.stream({
        model: config.model,
        messages: session.messages,
        systemPrompt: config.systemPrompt,
        tools: registry.toToolDefinitions(),
        ...(abortSignal ? { abortSignal } : {}),
      })) {
        switch (event.type) {
          case "text_delta": {
            content.push(textContent(event.text));
            const textEvent: AgentEvent = { type: "text", text: event.text };
            config.onEvent?.(textEvent);
            yield textEvent;
            break;
          }
          case "tool_call_start": {
            partialCalls.set(event.id, { id: event.id, name: event.name, argsText: "" });
            break;
          }
          case "tool_call_delta": {
            const partial = partialCalls.get(event.id);
            if (partial) {
              partial.argsText += event.arguments;
            }
            break;
          }
          case "tool_call_end": {
            const partial = partialCalls.get(event.id);
            if (!partial) {
              break;
            }
            partialCalls.delete(event.id);
            const call = toToolCallContent(partial);
            toolCalls.push(call);
            content.push(call);
            const toolCallEvent: AgentEvent = {
              type: "tool_call",
              name: call.name,
              args: call.arguments,
            };
            config.onEvent?.(toolCallEvent);
            yield toolCallEvent;
            break;
          }
          case "finish":
            finishReason = event.reason;
            break;
          case "error":
            throw event.error;
        }
      }

      const assistantMessage = createMessage("assistant", mergeAdjacentTextContent(content));
      session.messages.push(assistantMessage);

      const endEvent: AgentEvent = { type: "message_end", finishReason };
      config.onEvent?.(endEvent);
      yield endEvent;

      if (toolCalls.length === 0) {
        session.status = "completed";
        return;
      }

      doomLoopDetector.record(toolCalls);
      const results: ToolResultContent[] = [];
      for (const call of toolCalls) {
        const result = await executor.execute(
          call,
          {
            sessionId: session.id,
            messageId: assistantMessage.id,
            ...(abortSignal ? { abortSignal } : {}),
          },
          session,
        );
        results.push(result);
        const toolResultEvent: AgentEvent =
          result.isError === undefined
            ? {
                type: "tool_result",
                name: call.name,
                result: result.result,
              }
            : {
                type: "tool_result",
                name: call.name,
                result: result.result,
                isError: result.isError,
              };
        config.onEvent?.(toolResultEvent);
        yield toolResultEvent;
      }

      session.messages.push(createMessage("tool", results));
    }
  } catch (error) {
    const normalized = error instanceof Error ? error : new Error(String(error));
    session.status = "error";
    const errorEvent: AgentEvent = { type: "error", error: normalized };
    config.onEvent?.(errorEvent);
    yield errorEvent;
    throw normalized;
  }

  session.status = "error";
  const maxStepError = new Error(`Agent exceeded maxSteps=${maxSteps}`);
  const errorEvent: AgentEvent = { type: "error", error: maxStepError };
  config.onEvent?.(errorEvent);
  yield errorEvent;
  throw maxStepError;
}

function buildToolRegistry(session: Session, config: AgentRunConfig): ToolRegistry {
  const registry = new ToolRegistry();
  for (const tool of session.tools) {
    registry.unregister(tool.name);
    registry.register(tool);
  }
  for (const tool of config.tools ?? []) {
    registry.unregister(tool.name);
    registry.register(tool);
  }
  return registry;
}

function emitTextEvents(
  response: LLMOutput,
  onEvent: AgentRunConfig["onEvent"] | undefined,
): void {
  for (const item of response.content) {
    if (item.type === "text") {
      onEvent?.({ type: "text", text: item.text });
    }
  }
}

function toToolCallContent(partial: { id: string; name: string; argsText: string }): ToolCallContent {
  const args = parseToolArguments(partial.argsText);
  return toolCallContent(partial.name, args, partial.id);
}

function parseToolArguments(raw: string): unknown {
  if (raw.trim() === "") {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch {
    return { raw };
  }
}

function assertNotAborted(abortSignal: AbortSignal | undefined): void {
  if (abortSignal?.aborted) {
    throw new Error("Operation aborted.");
  }
}
