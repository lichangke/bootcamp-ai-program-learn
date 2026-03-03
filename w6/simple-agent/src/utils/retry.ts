export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableErrors: string[];
}

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 0,
  baseDelay: 250,
  maxDelay: 4_000,
  retryableErrors: [],
};

export async function withRetry<T>(fn: () => Promise<T>, config: RetryConfig): Promise<T> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= config.maxRetries; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      const normalizedError = normalizeError(error);
      lastError = normalizedError;
      if (!isRetryable(normalizedError, config.retryableErrors) || attempt === config.maxRetries) {
        throw normalizedError;
      }
      const delay = Math.min(config.baseDelay * Math.pow(2, attempt), config.maxDelay);
      await sleep(delay);
    }
  }

  throw lastError ?? new Error("Retry failed without explicit error.");
}

export function isRetryable(error: Error, retryableErrors: string[]): boolean {
  if (retryableErrors.length === 0) {
    return false;
  }

  return retryableErrors.some((pattern) => {
    const content = `${error.name}:${error.message}`;
    if (pattern === "*") {
      return true;
    }
    return content.includes(pattern);
  });
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function normalizeError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}
