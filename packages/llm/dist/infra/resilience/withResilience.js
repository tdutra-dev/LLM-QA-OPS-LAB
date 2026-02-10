export class TimeoutError extends Error {
    constructor(message = "Operation timed out") {
        super(message);
        this.name = "TimeoutError";
    }
}
function sleep(ms, signal) {
    return new Promise((resolve, reject) => {
        const id = setTimeout(resolve, ms);
        if (!signal)
            return;
        if (signal.aborted) {
            clearTimeout(id);
            return reject(signal.reason ?? new Error("Aborted"));
        }
        signal.addEventListener("abort", () => {
            clearTimeout(id);
            reject(signal.reason ?? new Error("Aborted"));
        }, { once: true });
    });
}
function addJitter(delayMs, jitterRatio) {
    const delta = delayMs * jitterRatio;
    const min = delayMs - delta;
    const max = delayMs + delta;
    return Math.max(0, Math.floor(min + Math.random() * (max - min)));
}
function expBackoff(attempt, baseDelayMs, maxDelayMs) {
    const raw = baseDelayMs * Math.pow(2, attempt - 1);
    return Math.min(maxDelayMs, raw);
}
function defaultShouldRetry(err) {
    if (!err)
        return { retry: false };
    // TimeoutError creato da noi
    if (err?.name === "TimeoutError")
        return { retry: true, reason: "timeout" };
    // Alcuni ambienti / libs possono restituire AbortError
    if (err?.name === "AbortError")
        return { retry: true, reason: "aborted" };
    const status = err?.status ?? err?.response?.status;
    if (status === 429)
        return { retry: true, reason: "rate_limit" };
    if (status >= 500 && status <= 599)
        return { retry: true, reason: "server_5xx" };
    const code = err?.code;
    const transientCodes = new Set([
        "ETIMEDOUT",
        "ECONNRESET",
        "EAI_AGAIN",
        "ENOTFOUND",
        "ECONNREFUSED",
    ]);
    if (code && transientCodes.has(code))
        return { retry: true, reason: `network_${code}` };
    return { retry: false, reason: "non_retryable" };
}
/**
 * operation riceve un AbortSignal per cancellare la request (fetch/OpenAI ecc.)
 */
export async function withResilience(operation, opts) {
    const { timeoutMs, maxAttempts, baseDelayMs, maxDelayMs, jitterRatio = 0.2, shouldRetry = defaultShouldRetry, onAttempt, onRetry, } = opts;
    let lastErr;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        onAttempt?.({ attempt });
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            controller.abort(new TimeoutError(`Timeout after ${timeoutMs}ms`));
        }, timeoutMs);
        try {
            const result = await operation({ signal: controller.signal });
            clearTimeout(timeoutId);
            return result;
        }
        catch (err) {
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
            await sleep(delayWithJitter);
        }
    }
    throw lastErr ?? new Error("Unknown error");
}
//# sourceMappingURL=withResilience.js.map