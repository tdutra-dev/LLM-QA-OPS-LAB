export class InMemoryMetrics {
    attempts = 0;
    retries = 0;
    fallbacks = 0;
    recoveryAttempts = 0;
    recoverySuccesses = 0;
    requests = 0;
    incAttempts() { this.attempts++; }
    incRetries() { this.retries++; }
    incFallbacks() { this.fallbacks++; }
    incRecoveryAttempts() { this.recoveryAttempts++; }
    incRecoverySuccesses() { this.recoverySuccesses++; }
    incRequests() { this.requests++; }
    snapshot() {
        return {
            attempts: this.attempts,
            retries: this.retries,
            fallbacks: this.fallbacks,
            recoveryAttempts: this.recoveryAttempts,
            recoverySuccesses: this.recoverySuccesses,
            requests: this.requests,
        };
    }
}
//# sourceMappingURL=InMemoryMetrics.js.map