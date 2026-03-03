import { randomUUID } from "node:crypto";

import type { Tool } from "../tool/types.ts";
import type { Message } from "./message.ts";

export interface ModelConfig {
  name: string;
  maxTokens?: number;
  temperature?: number;
}

export type SessionStatus = "idle" | "running" | "completed" | "error";

export interface Session {
  id: string;
  messages: Message[];
  systemPrompt: string;
  model: ModelConfig;
  tools: Tool[];
  status: SessionStatus;
}

export interface CreateSessionInput {
  id?: string;
  messages?: Message[];
  systemPrompt: string;
  model: ModelConfig;
  tools?: Tool[];
}

export function createSession(input: CreateSessionInput): Session {
  return {
    id: input.id ?? randomUUID(),
    messages: input.messages ?? [],
    systemPrompt: input.systemPrompt,
    model: input.model,
    tools: input.tools ?? [],
    status: "idle",
  };
}

export class SessionStore {
  private readonly sessions = new Map<string, Session>();

  create(input: CreateSessionInput): Session {
    const session = createSession(input);
    this.sessions.set(session.id, session);
    return session;
  }

  get(id: string): Session | undefined {
    return this.sessions.get(id);
  }

  set(session: Session): void {
    this.sessions.set(session.id, session);
  }

  delete(id: string): boolean {
    return this.sessions.delete(id);
  }

  list(): Session[] {
    return [...this.sessions.values()];
  }
}
