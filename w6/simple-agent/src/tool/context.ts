export interface ExecutionContext {
  sessionId: string;
  messageId: string;
  abortSignal?: AbortSignal;
}
