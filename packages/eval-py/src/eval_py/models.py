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