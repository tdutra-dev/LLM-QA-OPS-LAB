export declare class InMemoryMetrics {
    attempts: number;
    retries: number;
    fallbacks: number;
    recoveryAttempts: number;
    recoverySuccesses: number;
    requests: number;
    incAttempts(): void;
    incRetries(): void;
    incFallbacks(): void;
    incRecoveryAttempts(): void;
    incRecoverySuccesses(): void;
    incRequests(): void;
    snapshot(): {
        attempts: number;
        retries: number;
        fallbacks: number;
        recoveryAttempts: number;
        recoverySuccesses: number;
        requests: number;
    };
}
//# sourceMappingURL=InMemoryMetrics.d.ts.map