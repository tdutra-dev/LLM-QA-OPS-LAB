import { metrics } from "../metrics/index.js";

export type RetryDecision = {
  retry: boolean;
  reason?: string;
};

export type ResilienceOptions = {
  timeoutMs: number;
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  jitterRatio?: number;
  shouldRetry?: (err: unknown) => RetryDecision;

  // hooks opzionali per osservabilità
  onAttempt?: (info: { attempt: number }) => void;
  onRetry?: (info: {
    attempt: number;
    delayMs: number;
    decision: RetryDecision;
    err: unknown;
  }) => void;
};

export class TimeoutError extends Error {
  constructor(message = "Operation timed out") {
    super(message);
    this.name = "TimeoutError";
  }
}

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const id = setTimeout(resolve, ms);

    if (!signal) return;

    if (signal.aborted) {
      clearTimeout(id);
      return reject(signal.reason ?? new Error("Aborted"));
    }

    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(id);
        reject(signal.reason ?? new Error("Aborted"));
      },
      { once: true }
    );
  });
}

function addJitter(delayMs: number, jitterRatio: number) {
  const delta = delayMs * jitterRatio;
  const min = delayMs - delta;
  const max = delayMs + delta;
  return Math.max(0, Math.floor(min + Math.random() * (max - min)));
}

function expBackoff(attempt: number, baseDelayMs: number, maxDelayMs: number) {
  const raw = baseDelayMs * Math.pow(2, attempt - 1);
  return Math.min(maxDelayMs, raw);
}

function defaultShouldRetry(err: any): RetryDecision {
  if (!err) return { retry: false };

  // TimeoutError creato da noi
  if (err?.name === "TimeoutError") return { retry: true, reason: "timeout" };

  // Alcuni ambienti / libs possono restituire AbortError
  if (err?.name === "AbortError") return { retry: true, reason: "aborted" };

  const status = err?.status ?? err?.response?.status;
  if (status === 429) return { retry: true, reason: "rate_limit" };
  if (status >= 500 && status <= 599) return { retry: true, reason: "server_5xx" };

  const code = err?.code;
  const transientCodes = new Set([
    "ETIMEDOUT",
    "ECONNRESET",
    "EAI_AGAIN",
    "ENOTFOUND",
    "ECONNREFUSED",
  ]);
  if (code && transientCodes.has(code)) return { retry: true, reason: `network_${code}` };

  return { retry: false, reason: "non_retryable" };
}

/**
 * operation riceve un AbortSignal per cancellare la request (fetch/OpenAI ecc.)
 */
export async function withResilience<T>(
  operation: (ctx: { signal: AbortSignal }) => Promise<T>,
  opts: ResilienceOptions
): Promise<T> {
  const {
    timeoutMs,
    maxAttempts,
    baseDelayMs,
    maxDelayMs,
    jitterRatio = 0.2,
    shouldRetry = defaultShouldRetry,
    onAttempt,
    onRetry,
  } = opts;

  let lastErr: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    //Increase the attempt count at the beginning of each loop, 
    // so that it counts all attempts including the first one
    metrics.incAttempts();

    onAttempt?.({ attempt });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort(new TimeoutError(`Timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    try {
      const result = await operation({ signal: controller.signal });
      clearTimeout(timeoutId);
      return result;
    } catch (err) {
      clearTimeout(timeoutId);
      lastErr = err;

      const decision = shouldRetry(err);
      const isLast = attempt === maxAttempts;

      if (!decision.retry || isLast) {
        throw err;
      }

      const delay = expBackoff(attempt, baseDelayMs, maxDelayMs);
      const delayWithJitter = addJitter(delay, jitterRatio);

      onRetry?.({ attempt, delayMs: delayWithJitter, decision, err });
      // Increase the retry count only if a new attempt will actually be made
      metrics.incRetries();

      await sleep(delayWithJitter);
    }
  }

  throw lastErr ?? new Error("Unknown error");
}
