export type HealthStatus = "OK" | "WARN" | "CRITICAL";
export declare function evaluateHealth(input: {
    requests: number;
    attempts: number;
    retries: number;
    fallbacks: number;
    recoveryAttempts: number;
    recoverySuccesses: number;
}): {
    status: HealthStatus;
    issues: string[];
    actions: string[];
};
//# sourceMappingURL=health.d.ts.map