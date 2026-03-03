import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  Agent,
  OpenAIResponsesLLMClient,
  createMessage,
  textContent,
} from "../src/index.ts";

interface CodexAuth {
  OPENAI_API_KEY?: string;
}

interface CodexConfig {
  model: string;
  baseUrl: string;
}

async function loadCodexAuthAndConfig(): Promise<{ apiKey: string; model: string; baseUrl: string }> {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  const projectRoot = resolve(__dirname, "..", "..", "..");
  const authPath = resolve(projectRoot, ".codex", "auth.json");
  const configPath = resolve(projectRoot, ".codex", "config.toml");

  const authRaw = await readFile(authPath, "utf8");
  const auth = JSON.parse(authRaw) as CodexAuth;
  if (!auth.OPENAI_API_KEY) {
    throw new Error("Missing OPENAI_API_KEY in .codex/auth.json");
  }

  const configRaw = await readFile(configPath, "utf8");
  const config = parseCodexConfig(configRaw);
  return {
    apiKey: auth.OPENAI_API_KEY,
    model: config.model,
    baseUrl: config.baseUrl,
  };
}

function parseCodexConfig(content: string): CodexConfig {
  const model = pick(content, /model\s*=\s*"([^"]+)"/);
  const provider = pick(content, /model_provider\s*=\s*"([^"]+)"/);
  const providerEscaped = provider.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const section = new RegExp(
    `\\[model_providers\\.${providerEscaped}\\][\\s\\S]*?base_url\\s*=\\s*"([^"]+)"`,
  );
  const baseUrl = pick(content, section);
  return { model, baseUrl };
}

function pick(content: string, pattern: RegExp): string {
  const value = content.match(pattern)?.[1];
  if (!value) {
    throw new Error(`Cannot parse config value by pattern: ${pattern}`);
  }
  return value;
}

const { apiKey, model, baseUrl } = await loadCodexAuthAndConfig();
const llm = new OpenAIResponsesLLMClient({
  apiKey,
  baseUrl,
  requestTimeoutMs: 45_000,
});

const agent = new Agent(llm, {
  model,
  systemPrompt: "You are concise. Reply with one short sentence.",
});

const session = agent.createSession({
  messages: [
    createMessage("user", [textContent("请回复：SIMPLE_AGENT_LIVE_OK。不要附加其它内容。")]),
  ],
});

await agent.run(session);
const last = session.messages.at(-1);
const text = last?.content.find((item) => item.type === "text");

if (!text || text.type !== "text") {
  throw new Error("Live API smoke test failed: no text response.");
}

console.log(text.text);
