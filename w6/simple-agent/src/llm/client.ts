import type { Message, MessageContent, ToolCallContent } from "../session/message.ts";
import {
  mergeAdjacentTextContent,
  toolCallContent,
  textContent,
} from "../session/message.ts";
import type { ToolDefinition } from "../tool/types.ts";
import { normalizeError } from "../utils/retry.ts";

export interface Usage {
  inputTokens: number;
  outputTokens: number;
}

export interface LLMInput {
  model: string;
  messages: Message[];
  systemPrompt: string;
  tools: ToolDefinition[];
  abortSignal?: AbortSignal;
}

export interface LLMOutput {
  content: MessageContent[];
  finishReason: "stop" | "tool_calls" | "max_tokens" | "error";
  usage: Usage;
}

export type LLMEvent =
  | { type: "text_delta"; text: string }
  | { type: "tool_call_start"; id: string; name: string }
  | { type: "tool_call_delta"; id: string; arguments: string }
  | { type: "tool_call_end"; id: string }
  | { type: "finish"; reason: LLMOutput["finishReason"]; usage: Usage }
  | { type: "error"; error: Error };

export interface LLMClient {
  generate(input: LLMInput): Promise<LLMOutput>;
  stream(input: LLMInput): AsyncGenerator<LLMEvent>;
}

interface PartialToolCall {
  id: string;
  name: string;
  argumentsText: string;
}

export async function collectLLMStream(stream: AsyncGenerator<LLMEvent>): Promise<LLMOutput> {
  const content: MessageContent[] = [];
  const partialCalls = new Map<string, PartialToolCall>();
  let finishReason: LLMOutput["finishReason"] = "stop";
  let usage: Usage = { inputTokens: 0, outputTokens: 0 };

  try {
    for await (const event of stream) {
      switch (event.type) {
        case "text_delta":
          content.push(textContent(event.text));
          break;
        case "tool_call_start":
          partialCalls.set(event.id, {
            id: event.id,
            name: event.name,
            argumentsText: "",
          });
          break;
        case "tool_call_delta": {
          const call = partialCalls.get(event.id);
          if (call) {
            call.argumentsText += event.arguments;
          }
          break;
        }
        case "tool_call_end": {
          const call = partialCalls.get(event.id);
          if (!call) {
            continue;
          }
          partialCalls.delete(event.id);
          content.push(toToolCall(call));
          break;
        }
        case "finish":
          finishReason = event.reason;
          usage = event.usage;
          break;
        case "error":
          throw event.error;
      }
    }
  } catch (error) {
    throw normalizeError(error);
  }

  return {
    content: mergeAdjacentTextContent(content),
    finishReason,
    usage,
  };
}

function toToolCall(call: PartialToolCall): ToolCallContent {
  const parsed = parseArguments(call.argumentsText);
  return toolCallContent(call.name, parsed, call.id);
}

function parseArguments(value: string): unknown {
  if (!value.trim()) {
    return {};
  }
  try {
    return JSON.parse(value);
  } catch {
    return { raw: value };
  }
}
