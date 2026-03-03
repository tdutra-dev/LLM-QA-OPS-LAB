from __future__ import annotations

from .models import EvaluateRequest, EvaluateResponse, KPIs


def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    total = max(len(req.results), 1)
    failed = sum(1 for r in req.results if not r.ok)

    error_rate = failed / total
    avg_latency = sum(r.latencyMs for r in req.results) / total
    fallback_rate = sum(1 for r in req.results if r.usedFallback) / total

    if error_rate <= 0.05:
        health = "OK"
    elif error_rate <= 0.15:
        health = "DEGRADED"
    else:
        health = "CRITICAL"

    return EvaluateResponse(
        health=health,
        kpis=KPIs(
            errorRate=error_rate,
            avgLatency=avg_latency,
            fallbackRate=fallback_rate,
        ),
        reason=f"Error rate: {error_rate * 100:.1f}%",
    )