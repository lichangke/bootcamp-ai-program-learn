import { createMessage, textContent, type Message } from "../session/message.ts";

export interface MessageCompressor {
  compress(messages: Message[]): Promise<Message[]>;
}

export interface SlidingWindowCompressorOptions {
  keepFirst: number;
  keepLast: number;
}

export class SlidingWindowMessageCompressor implements MessageCompressor {
  private readonly keepFirst: number;
  private readonly keepLast: number;

  constructor(options: SlidingWindowCompressorOptions = { keepFirst: 2, keepLast: 8 }) {
    this.keepFirst = options.keepFirst;
    this.keepLast = options.keepLast;
  }

  async compress(messages: Message[]): Promise<Message[]> {
    if (messages.length <= this.keepFirst + this.keepLast) {
      return messages;
    }

    const head = messages.slice(0, this.keepFirst);
    const tail = messages.slice(-this.keepLast);
    const middle = messages.slice(this.keepFirst, -this.keepLast);
    const summary = summarizeMessages(middle);
    return [...head, createMessage("assistant", [textContent(summary)]), ...tail];
  }
}

function summarizeMessages(messages: Message[]): string {
  const lines: string[] = [];
  for (const message of messages) {
    const textParts = message.content
      .filter((block) => block.type === "text")
      .map((block) => block.text.trim())
      .filter((text) => text.length > 0);

    const toolCalls = message.content
      .filter((block) => block.type === "tool_call")
      .map((block) => block.name);

    const toolResults = message.content.filter((block) => block.type === "tool_result").length;

    if (textParts.length > 0) {
      lines.push(`${message.role}: ${textParts.join(" ").slice(0, 100)}`);
    }
    if (toolCalls.length > 0) {
      lines.push(`${message.role}: tool_calls=[${toolCalls.join(", ")}]`);
    }
    if (toolResults > 0) {
      lines.push(`${message.role}: tool_results=${toolResults}`);
    }
  }
  return `Compressed history summary:\n${lines.join("\n")}`;
}
