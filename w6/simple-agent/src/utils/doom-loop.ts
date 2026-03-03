import type { ToolCallContent } from "../session/message.ts";

export class DoomLoopError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DoomLoopError";
  }
}

export class DoomLoopDetector {
  private lastSignature: string | undefined;
  private repeatCount = 0;
  private readonly maxRepeats: number;

  constructor(maxRepeats: number = 3) {
    this.maxRepeats = maxRepeats;
  }

  record(toolCalls: ToolCallContent[]): void {
    const signature = this.createSignature(toolCalls);
    if (signature === this.lastSignature) {
      this.repeatCount += 1;
    } else {
      this.lastSignature = signature;
      this.repeatCount = 1;
    }

    if (this.repeatCount > this.maxRepeats) {
      throw new DoomLoopError(
        `Detected repeated tool call pattern ${this.repeatCount} times: ${signature}`,
      );
    }
  }

  private createSignature(toolCalls: ToolCallContent[]): string {
    return JSON.stringify(
      toolCalls.map((call) => ({
        name: call.name,
        args: call.arguments,
      })),
    );
  }
}
