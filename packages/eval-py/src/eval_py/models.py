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

HallucinationRisk = Literal["low", "medium", "high"]


# ─── Fase 3: Batch Analysis models ───────────────────────────────────────────

class BatchEventSummary(BaseModel):
    """
    Aggregato per service nel risultato dell'analisi batch.
    Prodotto dal LLM (o dal fallback rule-based) dopo aver letto tutti gli eventi.
    """
    service: str
    count: int
    dominant_severity: Severity      # il livello più grave tra gli eventi del service
    incident_types: list[str]        # tipi di incident unici visti per questo service


class BatchAnalysisResult(BaseModel):
    """
    Risultato dell'analisi batch LLM su una finestra temporale di incident.

    Questa è la struttura dati centrale della Fase 3:
    - event_count: quanti eventi ha analizzato il LLM in questa chiamata
    - overall_assessment: il giudizio complessivo del LLM sulla situazione
    - critical_pattern: il pattern più critico identificato (null se nessuno)
    - recommended_actions: azioni suggerite dal LLM
    - hallucination_risk: auto-valutazione del LLM → prima metrica di evaluation
    - confidence_score: confidence 0-100 del LLM → segunda metrica di evaluation
    - llm_used: False se il fallback rule-based è stato usato (no OPENAI_API_KEY)
    """
    batch_id: str
    analyzed_at: str                          # ISO 8601 UTC
    event_count: int = Field(ge=0)
    window_seconds: int = Field(ge=0)
    services_affected: list[str]
    overall_assessment: str
    critical_pattern: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    events_by_service: list[BatchEventSummary] = Field(default_factory=list)
    hallucination_risk: HallucinationRisk = "medium"
    confidence_score: int = Field(ge=0, le=100, default=50)
    llm_used: bool = True
    raw_llm_response: str | None = None       # JSON grezzo per audit/debug


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


# ─── Fase 2: Ingestion layer models ──────────────────────────────────────────

class IngestResponse(BaseModel):
    """
    Response returned by all /ingest/* endpoints.

    Confirms that the raw payload was successfully normalized and evaluated.
    The incident_id can be used to retrieve the full record later.
    """
    incident_id: str
    source_system: str
    service: str
    severity: str
    incident_type: str
    evaluation_status: EvaluationStatus
    evaluation_score: int
    suggested_action: SuggestedAction | None = None


# ─── Step 12: RAG models ──────────────────────────────────────────────────────

class SimilarIncidentResponse(BaseModel):
    """A past incident retrieved via pgvector similarity search."""
    recordId: str
    workflow: str
    incidentType: str
    severity: str
    summary: str
    suggestedAction: str | None
    evalStatus: str
    evalScore: int
    similarity: float   # 0.0–1.0, higher = more similar


class RagEvaluationResult(EvaluationResult):
    """
    Extended evaluation result enriched with RAG context.

    Adds:
    - similarIncidents: top-K past incidents retrieved via pgvector
    - ragContextUsed:   whether retrieval found at least one similar incident
    - embeddingStored:  whether the embedding for this incident was persisted
    """
    similarIncidents: list[SimilarIncidentResponse] = Field(default_factory=list)
    ragContextUsed: bool = False
    embeddingStored: bool = False


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


# ─── Step 8: Agent Loop models ────────────────────────────────────────────────

class AgentStatus(BaseModel):
    """
    Real-time status of the autonomous agent loop.

    Returned by GET /agent/status and embedded in start/stop responses.
    Gives operators a live view of how many cycles the loop has completed
    and how many autonomous actions it has executed since it was started.
    """
    running: bool
    cyclesCompleted: int
    actionsExecuted: int
    startedAt: str | None = None         # ISO 8601, None if never started
    lastCycleAt: str | None = None       # ISO 8601, None if no cycle yet
    intervalSeconds: float | None = None  # polling interval currently in use


# ─── Step 9: Tool Calling models ──────────────────────────────────────────────

class ToolCallArguments(BaseModel):
    """Structured arguments for a tool call, as chosen by the LLM."""
    workflow: str
    severity: str
    reason: str
    context: dict[str, Any] | None = None


class ToolCall(BaseModel):
    """Single tool call made by the LLM via OpenAI function calling."""
    id: str                      # OpenAI tool_call_id
    function: str                # e.g. "escalate", "monitor", "retry"
    arguments: ToolCallArguments


class ToolExecutionResult(BaseModel):
    """Result of executing one tool call."""
    toolCallId: str
    function: str
    outcome: ActionOutcome       # success | failed | skipped
    detail: str
    executedAt: str


class ToolCallingEvaluationResult(BaseModel):
    """Response from the tool-calling evaluation path."""
    status: EvaluationStatus
    score: int = Field(ge=0, le=100)
    summary: str
    reasoning: str | None = None
    toolCalls: list[ToolCall]    # LLM-chosen tools
    toolResults: list[ToolExecutionResult]  # execution results
    tags: list[str] | None = None


class ToolCallLog(BaseModel):
    """Audit record for tool-calling evaluations."""
    logId: str                   # e.g. "tlog_abcdef12"
    recordId: str                # links to EvaluationRecord
    executedAt: str              # ISO 8601
    llmModel: str                # e.g. "gpt-4o-mini"
    toolCallsJson: str           # JSON array of ToolCall objects
    totalTools: int              # count of tools called
    successfulTools: int         # count with outcome="success"
    workflow: str
    severity: str