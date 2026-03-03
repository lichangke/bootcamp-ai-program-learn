import type { LLMClient } from "../llm/client.ts";
import type { PermissionManager } from "../permission/manager.ts";
import type { Message } from "../session/message.ts";
import { createSession, type CreateSessionInput, type Session } from "../session/session.ts";
import type { Tool } from "../tool/types.ts";
import type { MessageCompressor } from "../utils/message-compressor.ts";
import type { RetryConfig } from "../utils/retry.ts";
import { runAgent, streamAgent } from "./loop.ts";

export type AgentEvent =
  | { type: "message_start"; role: "assistant" }
  | { type: "text"; text: string }
  | { type: "tool_call"; name: string; args: unknown }
  | { type: "tool_result"; name: string; result: string; isError?: boolean }
  | { type: "message_end"; finishReason: string }
  | { type: "error"; error: Error };

export interface AgentConfig {
  model: string;
  systemPrompt: string;
  tools?: Tool[];
  maxSteps?: number;
  onEvent?: (event: AgentEvent) => void;
  permissionManager?: PermissionManager;
  retryConfig?: RetryConfig;
  messageCompressor?: MessageCompressor;
  compressionTriggerMessages?: number;
  doomLoopMaxRepeats?: number;
}

export interface AgentRunConfig extends AgentConfig {
  llmClient: LLMClient;
}

export interface RunAgentOptions {
  maxSteps?: number;
  abortSignal?: AbortSignal;
}

export class Agent {
  private readonly llmClient: LLMClient;
  private readonly config: AgentConfig;

  constructor(
    llmClient: LLMClient,
    config: AgentConfig,
  ) {
    this.llmClient = llmClient;
    this.config = config;
  }

  createSession(input?: Omit<CreateSessionInput, "model" | "systemPrompt" | "tools">): Session {
    const sessionInput: CreateSessionInput = {
      ...input,
      model: { name: this.config.model },
      systemPrompt: this.config.systemPrompt,
      ...(this.config.tools ? { tools: this.config.tools } : {}),
    };
    return createSession(sessionInput);
  }

  async run(session: Session, options?: RunAgentOptions): Promise<Message[]> {
    const runConfig: AgentRunConfig = {
      ...this.config,
      llmClient: this.llmClient,
      ...(options?.maxSteps !== undefined
        ? { maxSteps: options.maxSteps }
        : this.config.maxSteps !== undefined
          ? { maxSteps: this.config.maxSteps }
          : {}),
    };

    return runAgent(session, runConfig, options?.abortSignal);
  }

  async *stream(session: Session, options?: RunAgentOptions): AsyncGenerator<AgentEvent> {
    const runConfig: AgentRunConfig = {
      ...this.config,
      llmClient: this.llmClient,
      ...(options?.maxSteps !== undefined
        ? { maxSteps: options.maxSteps }
        : this.config.maxSteps !== undefined
          ? { maxSteps: this.config.maxSteps }
          : {}),
    };

    for await (const event of streamAgent(
      session,
      runConfig,
      options?.abortSignal,
    )) {
      yield event;
    }
  }
}
