import { exec } from "node:child_process";
import { promisify } from "node:util";

import type { Tool } from "../types.ts";

const execAsync = promisify(exec);

interface BashArgs {
  command: string;
  timeoutMs?: number;
}

export function createBashTool(defaultTimeoutMs: number = 5_000): Tool {
  return {
    name: "bash",
    description: "Run a shell command and return stdout/stderr.",
    parameters: {
      type: "object",
      properties: {
        command: { type: "string", description: "Shell command to run" },
        timeoutMs: { type: "number", description: "Timeout in milliseconds" },
      },
      required: ["command"],
      additionalProperties: false,
    },
    execute: async (args) => {
      const input = args as Partial<BashArgs>;
      if (!input.command) {
        return { output: "Missing required field: command", error: "INVALID_ARGS" };
      }

      try {
        const result = await execAsync(input.command, {
          timeout: input.timeoutMs ?? defaultTimeoutMs,
          windowsHide: true,
        });
        const text = [result.stdout, result.stderr].filter(Boolean).join("\n");
        return { output: text || "(empty output)" };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { output: message, error: "EXECUTION_FAILED" };
      }
    },
  };
}
