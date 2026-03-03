import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const examplesRoot = resolve(__dirname, "..", "examples");

const examples = [
  "basic-custom-tools.ts",
  "streaming.ts",
  "mcp-tools.ts",
  "live-api-smoke.ts",
];

let failed = 0;

for (const file of examples) {
  const startedAt = Date.now();
  process.stdout.write(`\n[examples] running ${file} ...\n`);
  try {
    const href = `${pathToFileURL(resolve(examplesRoot, file)).href}?t=${Date.now()}`;
    await import(href);
    const elapsed = Date.now() - startedAt;
    process.stdout.write(`[examples] ok ${file} (${elapsed}ms)\n`);
  } catch (error) {
    failed += 1;
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`[examples] failed ${file}: ${message}\n`);
  }
}

if (failed > 0) {
  process.exitCode = 1;
  throw new Error(`Example tests failed: ${failed}`);
}

process.stdout.write("\n[examples] all examples passed.\n");
