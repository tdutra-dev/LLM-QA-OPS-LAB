from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Query

from .engine import evaluate
from .models import (
    EvaluationRecord,
    EvaluationRequest,
    EvaluationResult,
    MetricsSummary,
)
from .store import IncidentStore, get_store

app = FastAPI(
    title="LLM-QA-OPS Evaluation Service",
    version="0.2.0",
    description=(
        "Evaluates LLM pipeline incidents and exposes aggregated metrics. "
        "Part of the LLM-QA-OPS-LAB roadmap — Step 2: FastAPI expanded."
    ),
)


# ── Background task ───────────────────────────────────────────────────────────

def _persist_record(record: EvaluationRecord) -> None:
    """
    Runs AFTER the HTTP response has already been sent to the client.
    Currently just logs — in Step 3 this will write to PostgreSQL.

    FastAPI's BackgroundTasks guarantees this runs in the same process
    but outside the request/response lifecycle.
    """
    print(
        f"[bg] record saved | id={record.recordId}"
        f" | workflow={record.incident.workflow}"
        f" | status={record.result.status}"
        f" | score={record.result.score}"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    """Liveness probe — used by Docker and Kubernetes health checks."""
    return {"status": "ok"}


@app.post("/evaluate", response_model=EvaluationResult, tags=["Evaluation"])
def evaluate_endpoint(
    req: EvaluationRequest,
    background_tasks: BackgroundTasks,
    store: IncidentStore = Depends(get_store),
) -> EvaluationResult:
    """
    Evaluate a single LLM pipeline incident.

    Saves the record to the in-memory store (later: PostgreSQL) via a
    background task so the response is returned immediately without waiting.
    """
    result = evaluate(req)

    record = EvaluationRecord(
        recordId=f"rec_{uuid4().hex[:8]}",
        receivedAt=datetime.now(timezone.utc).isoformat(),
        incident=req.incident,
        result=result,
    )

    store.save(record)

    # Schedule persistence AFTER the response is sent — non-blocking
    background_tasks.add_task(_persist_record, record)

    return result


@app.get("/incidents", response_model=list[EvaluationRecord], tags=["Incidents"])
def list_incidents(
    workflow: str | None = Query(default=None, description="Filter by workflow name"),
    status: str | None = Query(default=None, description="Filter by evaluation status: ok | needs_attention | critical"),
    limit: int = Query(default=50, ge=1, le=500, description="Max records to return (newest first)"),
    store: IncidentStore = Depends(get_store),
) -> list[EvaluationRecord]:
    """
    List stored evaluation records, newest first.

    Supports optional filtering by workflow name and/or evaluation status.
    In Step 3 this will query PostgreSQL with pagination and date ranges.
    """
    return store.get_all(workflow=workflow, status=status, limit=limit)


@app.get("/metrics", response_model=MetricsSummary, tags=["Metrics"])
def get_metrics(
    store: IncidentStore = Depends(get_store),
) -> MetricsSummary:
    """
    Aggregated metrics across all stored evaluations.

    Returns counts by status/severity, average score, top suggested actions.
    In Step 4 this computation will be powered by Pandas / Polars for
    richer time-series analytics and rolling averages.
    """
    return store.get_metrics()
