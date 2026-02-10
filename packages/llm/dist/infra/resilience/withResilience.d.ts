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
    onAttempt?: (info: {
        attempt: number;
    }) => void;
    onRetry?: (info: {
        attempt: number;
        delayMs: number;
        decision: RetryDecision;
        err: unknown;
    }) => void;
};
export declare class TimeoutError extends Error {
    constructor(message?: string);
}
/**
 * operation riceve un AbortSignal per cancellare la request (fetch/OpenAI ecc.)
 */
export declare function withResilience<T>(operation: (ctx: {
    signal: AbortSignal;
}) => Promise<T>, opts: ResilienceOptions): Promise<T>;
//# sourceMappingURL=withResilience.d.ts.map