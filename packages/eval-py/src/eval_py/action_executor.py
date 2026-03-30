"""
Step 7 — ActionExecutor: autonomous remediation engine.

Design
──────
The ActionExecutor is the "hands" of the agentic system.  After the evaluator
scores an incident and suggests an action, this module carries it out — without
waiting for a human to decide.

Each of the six SuggestedAction values maps to a dedicated handler that:
  • Applies a deterministic remediation strategy based on severity / status.
  • Returns an ActionResult dict with outcome ("success" | "failed" | "skipped")
    and a human-readable detail string suitable for the audit log.

Handlers are intentionally synchronous and free of side effects in the test
environment (no real network calls).  In production you would replace the
body of each handler with actual integrations:
  - monitor      → push metric to Prometheus / Datadog
  - retry        → call the API gateway to replay the failed request
  - inspect_*    → open a Jira/GitHub issue via their APIs
  - check_provider → HTTP GET to the provider's status page
  - escalate     → POST to PagerDuty / Slack webhook

Agentic loop position
─────────────────────
  POST /evaluate
       │
       ├─ evaluate() ──────────── LLM engine scores the incident
       │                          returns EvaluationResult { status, score,
       │                                                     suggestedAction }
       │
       └─ execute()   ──────────── ActionExecutor (this module)
                                   dispatches to handler
                                   returns ActionLog (persisted to PostgreSQL)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TypeAlias
from uuid import uuid4

from .models import ActionLog, EvaluationRecord

logger = logging.getLogger(__name__)

# ── Type alias for handler return value ───────────────────────────────────────
ActionResult: TypeAlias = dict[str, str]   # {"outcome": ..., "detail": ...}


# ── Individual action handlers ────────────────────────────────────────────────

def _handle_monitor(record: EvaluationRecord) -> ActionResult:
    """
    Activate enhanced monitoring for the affected workflow.

    In production: increase Prometheus scrape frequency, enable detailed
    tracing, or push a Datadog monitor tag for the workflow.
    """
    detail = (
        f"Enhanced monitoring activated for workflow '{record.incident.workflow}' "
        f"(stage: {record.incident.stage}). "
        f"Elevated alert threshold: severity≥{record.incident.severity}."
    )
    logger.info("[action:monitor] %s", detail)
    return {"outcome": "success", "detail": detail}


def _handle_retry(record: EvaluationRecord) -> ActionResult:
    """
    Schedule a retry of the failed pipeline stage.

    In production: push a retry message onto a task queue (Celery / SQS),
    or call the API gateway to replay the original request.
    Critical severity gets an immediate retry; others are deferred.
    """
    mode = "immediate" if record.incident.severity == "critical" else "deferred (60 s backoff)"
    detail = (
        f"Retry scheduled ({mode}) for workflow '{record.incident.workflow}' "
        f"at stage '{record.incident.stage}'. "
        f"Reason: {record.incident.message}."
    )
    logger.info("[action:retry] %s", detail)
    return {"outcome": "success", "detail": detail}


def _handle_inspect_prompt(record: EvaluationRecord) -> ActionResult:
    """
    Flag the prompt template associated with this workflow for human review.

    In production: open a GitHub issue or Jira ticket with the full incident
    context so a prompt engineer can investigate the degradation.
    """
    detail = (
        f"Prompt review ticket created for workflow '{record.incident.workflow}' "
        f"(category: {record.incident.category}, "
        f"incidentType: {record.incident.incidentType}). "
        f"Assignee: prompt-engineering-team."
    )
    logger.info("[action:inspect_prompt] %s", detail)
    return {"outcome": "success", "detail": detail}


def _handle_inspect_schema(record: EvaluationRecord) -> ActionResult:
    """
    Flag the output schema associated with this workflow for human review.

    In production: open a schema-validation Jira ticket with the incident's
    full context JSON attached.
    """
    detail = (
        f"Schema review ticket created for workflow '{record.incident.workflow}' "
        f"(stage: {record.incident.stage}, "
        f"incidentType: {record.incident.incidentType}). "
        f"Attach full incident payload for schema diff analysis."
    )
    logger.info("[action:inspect_schema] %s", detail)
    return {"outcome": "success", "detail": detail}


def _handle_check_provider(record: EvaluationRecord) -> ActionResult:
    """
    Probe the LLM provider health and record the result.

    In production: HTTP GET to the provider's status page (e.g.
    https://status.openai.com/api/v2/status.json), parse the response,
    and escalate further if the provider itself is degraded.
    """
    # Simulated probe — in production replace with requests.get(...)
    provider_status = "operational"  # simulated
    detail = (
        f"Provider health check completed for workflow '{record.incident.workflow}'. "
        f"Provider status: {provider_status}. "
        f"Source: {record.incident.source}. "
        f"Recommendation: {'escalate to provider support' if provider_status != 'operational' else 'monitor and retry'}."
    )
    logger.info("[action:check_provider] %s", detail)
    return {"outcome": "success", "detail": detail}


def _handle_escalate(record: EvaluationRecord) -> ActionResult:
    """
    Create a high-priority escalation for human operators.

    In production: POST to PagerDuty Events API v2, Slack webhook, or
    OpsGenie. Critical severity triggers an immediate page; high severity
    sends a Slack alert; others create a low-urgency ticket.
    """
    channel = {
        "critical": "PagerDuty (immediate page)",
        "high":     "Slack #ops-alerts",
        "medium":   "Jira (medium priority)",
        "low":      "Jira (low priority)",
    }.get(record.incident.severity, "Jira")

    detail = (
        f"Escalation triggered via {channel} for workflow '{record.incident.workflow}' "
        f"| severity: {record.incident.severity} "
        f"| score: {record.result.score} "
        f"| message: {record.incident.message[:120]}"
    )
    logger.warning("[action:escalate] %s", detail)
    return {"outcome": "success", "detail": detail}


# ── Dispatcher ────────────────────────────────────────────────────────────────

_HANDLERS = {
    "monitor":        _handle_monitor,
    "retry":          _handle_retry,
    "inspect_prompt": _handle_inspect_prompt,
    "inspect_schema": _handle_inspect_schema,
    "check_provider": _handle_check_provider,
    "escalate":       _handle_escalate,
}


def execute(record: EvaluationRecord) -> ActionLog | None:
    """
    Dispatch the suggested action for a completed evaluation record.

    Returns an ActionLog if an action was executed, or None if the evaluation
    status was 'ok' (no action needed — monitoring is skipped for healthy runs).

    Called from the POST /evaluate background task so it runs asynchronously
    after the HTTP response has already been returned to the client.
    """
    action_type = record.result.suggestedAction

    # No action required for healthy evaluations
    if record.result.status == "ok" or action_type is None:
        logger.debug(
            "[action:skip] record=%s status=ok — no action needed", record.recordId
        )
        return None

    handler = _HANDLERS.get(action_type)
    if handler is None:
        logger.error("[action:unknown] action_type=%s — no handler registered", action_type)
        result: ActionResult = {"outcome": "failed", "detail": f"No handler for action '{action_type}'"}
    else:
        try:
            result = handler(record)
        except Exception as exc:
            logger.exception("[action:error] action_type=%s record=%s", action_type, record.recordId)
            result = {"outcome": "failed", "detail": f"Handler raised: {exc}"}

    log = ActionLog(
        actionId=f"act_{uuid4().hex[:8]}",
        recordId=record.recordId,
        executedAt=datetime.now(timezone.utc).isoformat(),
        actionType=action_type,  # type: ignore[arg-type]
        outcome=result["outcome"],  # type: ignore[arg-type]
        detail=result["detail"],
        workflow=record.incident.workflow,
        severity=record.incident.severity,
    )

    logger.info(
        "[action:done] id=%s type=%s outcome=%s workflow=%s",
        log.actionId, log.actionType, log.outcome, log.workflow,
    )
    return log
