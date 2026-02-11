export function computeKPIs(m: {
  requests: number;
  attempts: number;
  retries: number;
  fallbacks: number;
  recoveryAttempts: number;
  recoverySuccesses: number;
}) {
  const safeDiv = (a: number, b: number) => (b === 0 ? 0 : a / b);

  return {
    retryRate: safeDiv(m.retries, m.attempts),
    fallbackRate: safeDiv(m.fallbacks, m.requests),
    recoverySuccessRate: safeDiv(m.recoverySuccesses, m.recoveryAttempts),
    avgAttemptsPerRequest: safeDiv(m.attempts, m.requests),
  };
}
