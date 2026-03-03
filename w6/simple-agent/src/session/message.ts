import { randomUUID } from "node:crypto";

export type MessageRole = "user" | "assistant" | "tool";

export interface Message {
  id: string;
  role: MessageRole;
  content: MessageContent[];
  createdAt: Date;
}

export type MessageContent = TextContent | ToolCallContent | ToolResultContent;

export interface TextContent {
  type: "text";
  text: string;
}

export interface ToolCallContent {
  type: "tool_call";
  id: string;
  name: string;
  arguments: unknown;
}

export interface ToolResultContent {
  type: "tool_result";
  toolCallId: string;
  result: string;
  isError?: boolean;
}

export function textContent(text: string): TextContent {
  return { type: "text", text };
}

export function toolCallContent(
  name: string,
  args: unknown,
  id: string = randomUUID(),
): ToolCallContent {
  return { type: "tool_call", id, name, arguments: args };
}

export function toolResultContent(
  toolCallId: string,
  result: string,
  isError?: boolean,
): ToolResultContent {
  return isError === undefined
    ? { type: "tool_result", toolCallId, result }
    : { type: "tool_result", toolCallId, result, isError };
}

export function createMessage(
  role: MessageRole,
  content: MessageContent[],
  id: string = randomUUID(),
): Message {
  return {
    id,
    role,
    content,
    createdAt: new Date(),
  };
}

export function isToolCallContent(content: MessageContent): content is ToolCallContent {
  return content.type === "tool_call";
}

export function isTextContent(content: MessageContent): content is TextContent {
  return content.type === "text";
}

export function mergeAdjacentTextContent(content: MessageContent[]): MessageContent[] {
  const merged: MessageContent[] = [];
  for (const block of content) {
    const last = merged.at(-1);
    if (last?.type === "text" && block.type === "text") {
      last.text += block.text;
      continue;
    }
    merged.push(block);
  }
  return merged;
}
