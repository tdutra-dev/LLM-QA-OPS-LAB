export declare class InMemoryMetrics {
    attempts: number;
    retries: number;
    fallbacks: number;
    recoveryAttempts: number;
    recoverySuccesses: number;
    incAttempts(): void;
    incRetries(): void;
    incFallbacks(): void;
    incRecoveryAttempts(): void;
    incRecoverySuccesses(): void;
    snapshot(): {
        attempts: number;
        retries: number;
        fallbacks: number;
        recoveryAttempts: number;
        recoverySuccesses: number;
    };
}
//# sourceMappingURL=InMemoryMetrics.d.ts.map