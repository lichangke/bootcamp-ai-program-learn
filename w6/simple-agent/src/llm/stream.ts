import type { LLMClient, LLMEvent, LLMInput, LLMOutput } from "./client.ts";
import { collectLLMStream } from "./client.ts";

export async function* streamLLM(client: LLMClient, input: LLMInput): AsyncGenerator<LLMEvent> {
  for await (const event of client.stream(input)) {
    yield event;
  }
}

export async function callLLM(client: LLMClient, input: LLMInput): Promise<LLMOutput> {
  return client.generate(input);
}

export async function callLLMViaStream(client: LLMClient, input: LLMInput): Promise<LLMOutput> {
  return collectLLMStream(streamLLM(client, input));
}
