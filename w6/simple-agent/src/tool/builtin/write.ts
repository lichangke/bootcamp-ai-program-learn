import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { Tool } from "../types.ts";

interface WriteArgs {
  path: string;
  content: string;
}

export function createWriteTool(allowedRoots: string[] = []): Tool {
  return {
    name: "write_file",
    description: "Write text content to disk.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Target file path" },
        content: { type: "string", description: "File content to write" },
      },
      required: ["path", "content"],
      additionalProperties: false,
    },
    execute: async (args) => {
      const input = args as Partial<WriteArgs>;
      if (!input.path || typeof input.content !== "string") {
        return { output: "Missing required fields: path/content", error: "INVALID_ARGS" };
      }

      const absolutePath = resolve(input.path);
      if (!isPathAllowed(absolutePath, allowedRoots)) {
        return { output: `Path not allowed: ${absolutePath}`, error: "PATH_NOT_ALLOWED" };
      }

      await mkdir(dirname(absolutePath), { recursive: true });
      await writeFile(absolutePath, input.content, "utf8");
      return { output: `Wrote ${input.content.length} bytes to ${absolutePath}` };
    },
  };
}

function isPathAllowed(path: string, allowedRoots: string[]): boolean {
  if (allowedRoots.length === 0) {
    return true;
  }
  return allowedRoots.some((root) => path.startsWith(resolve(root)));
}
