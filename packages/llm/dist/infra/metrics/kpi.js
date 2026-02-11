export function computeKPIs(m) {
    const safeDiv = (a, b) => (b === 0 ? 0 : a / b);
    return {
        retryRate: safeDiv(m.retries, m.attempts),
        fallbackRate: safeDiv(m.fallbacks, m.requests),
        recoverySuccessRate: safeDiv(m.recoverySuccesses, m.recoveryAttempts),
        avgAttemptsPerRequest: safeDiv(m.attempts, m.requests),
    };
}
//# sourceMappingURL=kpi.js.map