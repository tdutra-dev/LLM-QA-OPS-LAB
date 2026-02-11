import { kpiRules } from "./rules.js";
export function evaluateHealth(input) {
    const issues = [];
    const actions = [];
    const retryRate = input.attempts === 0 ? 0 : input.retries / input.attempts;
    const fallbackRate = input.requests === 0 ? 0 : input.fallbacks / input.requests;
    const recoveryFailRate = input.recoveryAttempts === 0
        ? 0
        : 1 - input.recoverySuccesses / input.recoveryAttempts;
    // Retry
    if (retryRate >= kpiRules.retryRateCritical)
        issues.push(`retry rate ${(retryRate * 100).toFixed(1)}% is CRITICAL`);
    else if (retryRate >= kpiRules.retryRateWarn)
        issues.push(`retry rate ${(retryRate * 100).toFixed(1)}% is high`);
    if (retryRate >= kpiRules.retryRateWarn) {
        actions.push("Investigate provider latency/timeouts (review timeoutMs and provider response times).");
        actions.push("If retries remain high, tune fallback policy or reduce maxAttempts to fail fast.");
    }
    // Fallback
    if (fallbackRate >= kpiRules.fallbackRateCritical)
        issues.push(`fallback rate ${(fallbackRate * 100).toFixed(1)}% is CRITICAL`);
    else if (fallbackRate >= kpiRules.fallbackRateWarn)
        issues.push(`fallback rate ${(fallbackRate * 100).toFixed(1)}% is high`);
    if (fallbackRate >= kpiRules.fallbackRateWarn) {
        actions.push("Primary provider may be unstable—check status, rate limits, and error responses.");
        actions.push("Consider routing traffic to secondary provider earlier or adding provider health checks.");
    }
    // Recovery failures
    if (recoveryFailRate >= kpiRules.recoveryFailRateCritical)
        issues.push(`recovery fail rate ${(recoveryFailRate * 100).toFixed(1)}% is CRITICAL`);
    else if (recoveryFailRate >= kpiRules.recoveryFailRateWarn)
        issues.push(`recovery fail rate ${(recoveryFailRate * 100).toFixed(1)}% is high`);
    if (recoveryFailRate >= kpiRules.recoveryFailRateWarn) {
        actions.push("Recovery prompt may be weak—review and strengthen the JSON repair prompt.");
        actions.push("Add golden tests for prompt outputs and consider a second repair strategy.");
    }
    let status = "OK";
    if (issues.some((i) => i.includes("CRITICAL")))
        status = "CRITICAL";
    else if (issues.length > 0)
        status = "WARN";
    return { status, issues, actions };
}
//# sourceMappingURL=health.js.map