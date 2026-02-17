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

    reset() {
        this.attempts = 0;
        this.retries = 0;
        this.fallbacks = 0;
        this.recoveryAttempts = 0;
        this.recoverySuccesses = 0;
        this.requests = 0;
    }

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
