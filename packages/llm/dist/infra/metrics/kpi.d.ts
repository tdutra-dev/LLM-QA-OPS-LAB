export declare function computeKPIs(m: {
    requests: number;
    attempts: number;
    retries: number;
    fallbacks: number;
    recoveryAttempts: number;
    recoverySuccesses: number;
}): {
    retryRate: number;
    fallbackRate: number;
    recoverySuccessRate: number;
    avgAttemptsPerRequest: number;
};
//# sourceMappingURL=kpi.d.ts.map