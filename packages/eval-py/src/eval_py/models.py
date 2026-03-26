from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IncidentType = Literal[
    "technical_error",
    "schema_error",
    "semantic_error",
    "degradation",
]

Severity = Literal["low", "medium", "high", "critical"]

EvaluationStatus = Literal["ok", "needs_attention", "critical"]

SuggestedAction = Literal[
    "monitor",
    "retry",
    "inspect_prompt",
    "inspect_schema",
    "check_provider",
    "escalate",
]

HealthStatus = Literal["healthy", "degraded", "unstable", "critical"]

HealthTrend = Literal["stable", "improving", "worsening"]


class StandardIncident(BaseModel):
    id: str
    timestamp: str
    workflow: str
    stage: str

    incidentType: IncidentType
    category: str
    severity: Severity

    source: str
    message: str
    context: dict[str, Any] | None = None


class RequestMeta(BaseModel):
    sourceSystem: str | None = None
    requestedBy: str | None = None
    correlationId: str | None = None


class EvaluationRequest(BaseModel):
    incident: StandardIncident
    requestMeta: RequestMeta | None = None


class EvaluationResult(BaseModel):
    status: EvaluationStatus
    score: int = Field(ge=0, le=100)
    summary: str
    reasoning: str | None = None
    suggestedAction: SuggestedAction | None = None
    tags: list[str] | None = None


class WorkflowHealth(BaseModel):
    workflow: str
    status: HealthStatus
    score: int = Field(ge=0, le=100)
    trend: HealthTrend
    recentIncidentCount: int = Field(ge=0)
    summary: str
    timestamp: str | None = None


# ─── Step 2: History + Metrics models ────────────────────────────────────────

class EvaluationRecord(BaseModel):
    """
    A single evaluation stored in memory (later: PostgreSQL in Step 3).
    Combines the original incident with its evaluation result and metadata.
    """
    recordId: str
    receivedAt: str          # ISO 8601 timestamp of when the request arrived
    incident: StandardIncident
    result: EvaluationResult


class StatusCount(BaseModel):
    status: EvaluationStatus
    count: int


class ActionCount(BaseModel):
    action: str
    count: int


class MetricsSummary(BaseModel):
    """
    Aggregated view of all evaluations stored in memory.
    In Step 4 we will compute this with Pandas/Polars for richer analytics.
    """
    totalEvaluations: int
    byStatus: list[StatusCount]          # e.g. [{"status": "critical", "count": 3}]
    averageScore: float
    bySeverity: dict[str, int]           # e.g. {"high": 4, "critical": 1}
    topSuggestedActions: list[ActionCount]
    workflows: list[str]                 # distinct workflow names seen


# ─── Step 4: Pandas + Polars analytics models ─────────────────────────────────

class DailyScoreTrend(BaseModel):
    """One data point: average evaluation score for a given day (Pandas)."""
    date: str          # ISO date string, e.g. "2025-01-15"
    avgScore: float
    count: int


class SeverityBucket(BaseModel):
    """Polars: count of evaluations per severity level."""
    severity: str
    count: int
    pct: float         # percentage of total (0–100)


class WorkflowFailureRate(BaseModel):
    """Polars: fraction of non-'ok' evaluations per workflow."""
    workflow: str
    total: int
    failed: int
    failureRate: float  # 0.0–1.0


class AnalyticsReport(BaseModel):
    """
    Rich analytics report computed by Pandas + Polars.

    - dailyScoreTrend   → Pandas: resample by day + rolling mean
    - rollingAvgScore   → Pandas: 7-evaluation rolling average (last 10 values)
    - severityDistrib   → Polars: group_by severity
    - workflowFailure   → Polars: group_by workflow, compute failure rate
    """
    totalRows: int
    computedBy: str                          # e.g. "pandas==3.0.1 polars==1.39.3"
    dailyScoreTrend: list[DailyScoreTrend]
    rollingAvgScore: list[float]             # last N rolling-avg values
    severityDistrib: list[SeverityBucket]
    workflowFailure: list[WorkflowFailureRate]


# ─── Step 7: ActionExecutor models ───────────────────────────────────────────

ActionOutcome = Literal["success", "failed", "skipped"]


class ActionLog(BaseModel):
    """
    Audit record of a single autonomous action executed by the ActionExecutor.

    Every POST /evaluate with a non-'ok' result produces one ActionLog entry.
    The full history is queryable via GET /actions, giving the system a
    complete audit trail of every autonomous decision it made.
    """
    actionId: str              # unique ID e.g. "act_a1b2c3d4"
    recordId: str              # which evaluation triggered this action
    executedAt: str            # ISO 8601 timestamp
    actionType: SuggestedAction
    outcome: ActionOutcome     # success | failed | skipped
    detail: str                # human-readable result summary
    workflow: str
    severity: str