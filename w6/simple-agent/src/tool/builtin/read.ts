import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import type { Tool } from "../types.ts";

interface ReadArgs {
  path: string;
  encoding?: BufferEncoding;
}

export function createReadTool(allowedRoots: string[] = []): Tool {
  return {
    name: "read_file",
    description: "Read file content from disk.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Absolute or relative file path" },
        encoding: { type: "string", description: "Text encoding, default utf8" },
      },
      required: ["path"],
      additionalProperties: false,
    },
    execute: async (args) => {
      const input = args as Partial<ReadArgs>;
      if (!input.path) {
        return { output: "Missing required field: path", error: "INVALID_ARGS" };
      }

      const absolutePath = resolve(input.path);
      if (!isPathAllowed(absolutePath, allowedRoots)) {
        return { output: `Path not allowed: ${absolutePath}`, error: "PATH_NOT_ALLOWED" };
      }

      const content = await readFile(absolutePath, { encoding: input.encoding ?? "utf8" });
      return { output: content };
    },
  };
}

function isPathAllowed(path: string, allowedRoots: string[]): boolean {
  if (allowedRoots.length === 0) {
    return true;
  }
  return allowedRoots.some((root) => path.startsWith(resolve(root)));
}
