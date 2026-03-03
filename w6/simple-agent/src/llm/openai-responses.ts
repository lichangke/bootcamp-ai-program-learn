import { randomUUID } from "node:crypto";

import {
  textContent,
  toolCallContent,
  type Message,
  type MessageContent,
  type ToolCallContent,
} from "../session/message.ts";
import type { ToolDefinition } from "../tool/types.ts";
import type { LLMClient, LLMEvent, LLMInput, LLMOutput, Usage } from "./client.ts";

export interface OpenAIResponsesClientOptions {
  baseUrl: string;
  apiKey: string;
  requestTimeoutMs?: number;
}

interface ResponsesUsage {
  input_tokens?: number;
  output_tokens?: number;
}

interface ResponsesMessageContent {
  type?: string;
  text?: string;
}

interface ResponsesOutputItem {
  type?: string;
  role?: string;
  content?: ResponsesMessageContent[];
  name?: string;
  arguments?: string;
  call_id?: string;
  id?: string;
}

interface ResponsesApiResult {
  status?: string;
  usage?: ResponsesUsage;
  output?: ResponsesOutputItem[];
}

export class OpenAIResponsesLLMClient implements LLMClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly requestTimeoutMs: number;

  constructor(options: OpenAIResponsesClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 30_000;
  }

  async generate(input: LLMInput): Promise<LLMOutput> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeoutMs);
    if (input.abortSignal) {
      input.abortSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }

    try {
      const response = await fetch(`${this.baseUrl}/v1/responses`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: input.model,
          input: toResponsesInput(input.messages, input.systemPrompt),
          tools: toResponsesTools(input.tools),
          max_output_tokens: 512,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Responses API failed (${response.status}): ${body.slice(0, 400)}`);
      }

      const data = (await response.json()) as ResponsesApiResult;
      const parsedContent = fromResponsesOutput(data.output ?? []);
      const finishReason = parsedContent.some((item) => item.type === "tool_call")
        ? "tool_calls"
        : data.status === "completed"
          ? "stop"
          : "error";

      return {
        content: parsedContent,
        finishReason,
        usage: toUsage(data.usage),
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  async *stream(input: LLMInput): AsyncGenerator<LLMEvent> {
    const output = await this.generate(input);
    for (const item of output.content) {
      if (item.type === "text") {
        yield { type: "text_delta", text: item.text };
      } else if (item.type === "tool_call") {
        const payload = JSON.stringify(item.arguments ?? {});
        yield { type: "tool_call_start", id: item.id, name: item.name };
        if (payload.length > 0) {
          yield { type: "tool_call_delta", id: item.id, arguments: payload };
        }
        yield { type: "tool_call_end", id: item.id };
      }
    }

    yield {
      type: "finish",
      reason: output.finishReason,
      usage: output.usage,
    };
  }
}

function toResponsesInput(messages: Message[], systemPrompt: string): Array<Record<string, unknown>> {
  const mapped = messages
    .map((message) => mapMessage(message))
    .filter((item): item is Record<string, unknown> => item !== null);

  // Push system instructions as the first input message for best compatibility.
  return [
    {
      role: "system",
      content: [{ type: "input_text", text: systemPrompt }],
    },
    ...mapped,
  ];
}

function mapMessage(message: Message): Record<string, unknown> | null {
  if (message.role === "user" || message.role === "assistant") {
    const text = extractTextAndToolTrace(message.content);
    if (!text) {
      return null;
    }
    return {
      role: message.role,
      content: [{ type: "input_text", text }],
    };
  }

  // For tool results, convert them to user-side function outputs in plain text.
  const resultText = message.content
    .filter((item) => item.type === "tool_result")
    .map((item) => {
      const status = item.isError ? "error" : "ok";
      return `tool_result:${item.toolCallId}:${status}:${item.result}`;
    })
    .join("\n");

  if (!resultText) {
    return null;
  }

  return {
    role: "user",
    content: [{ type: "input_text", text: resultText }],
  };
}

function extractTextAndToolTrace(content: MessageContent[]): string {
  const parts: string[] = [];
  for (const item of content) {
    if (item.type === "text") {
      parts.push(item.text);
    } else if (item.type === "tool_call") {
      parts.push(`tool_call:${item.name}:${JSON.stringify(item.arguments ?? {})}`);
    }
  }
  return parts.join("\n").trim();
}

function toResponsesTools(tools: ToolDefinition[]): Array<Record<string, unknown>> {
  return tools.map((tool) => ({
    type: "function",
    name: tool.name,
    description: tool.description,
    parameters: tool.inputSchema,
  }));
}

function fromResponsesOutput(output: ResponsesOutputItem[]): MessageContent[] {
  const content: MessageContent[] = [];
  for (const item of output) {
    if (item.type === "message") {
      for (const block of item.content ?? []) {
        if (block.type === "output_text" && typeof block.text === "string") {
          content.push(textContent(block.text));
        }
      }
      continue;
    }

    if (item.type === "function_call" && item.name) {
      content.push(
        toToolCall(
          item.name,
          item.arguments,
          item.call_id ?? item.id ?? randomUUID(),
        ),
      );
    }
  }
  return content;
}

function toToolCall(name: string, rawArguments: string | undefined, id: string): ToolCallContent {
  if (!rawArguments) {
    return toolCallContent(name, {}, id);
  }
  try {
    return toolCallContent(name, JSON.parse(rawArguments), id);
  } catch {
    return toolCallContent(name, { raw: rawArguments }, id);
  }
}

function toUsage(usage: ResponsesUsage | undefined): Usage {
  return {
    inputTokens: usage?.input_tokens ?? 0,
    outputTokens: usage?.output_tokens ?? 0,
  };
}
