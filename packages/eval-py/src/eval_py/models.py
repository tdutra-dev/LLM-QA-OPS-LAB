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