from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Query

from .database import Base, engine
from .analytics import build_analytics_report
from .engine import evaluate
from .models import (
    AnalyticsReport,
    EvaluationRecord,
    EvaluationRequest,
    EvaluationResult,
    MetricsSummary,
)
from .store import IncidentStore, get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: code before `yield` runs at startup, after yield at shutdown.

    At startup we create all SQLAlchemy tables if they don't exist yet.
    In production you would use Alembic migrations instead of create_all().
    """
    # Import ORM models so SQLAlchemy knows about them before create_all()
    from . import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("[startup] PostgreSQL tables ready")
    yield
    print("[shutdown] evaluation service stopped")


app = FastAPI(
    title="LLM-QA-OPS Evaluation Service",
    version="0.4.0",
    description=(
        "Evaluates LLM pipeline incidents and exposes aggregated metrics. "
        "Part of the LLM-QA-OPS-LAB roadmap — Step 4: Pandas + Polars analytics."
    ),
    lifespan=lifespan,
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
    """
    return store.get_metrics()


@app.get("/analytics", response_model=AnalyticsReport, tags=["Analytics"])
def get_analytics(
    store: IncidentStore = Depends(get_store),
) -> AnalyticsReport:
    """
    Rich analytics report powered by **Pandas** and **Polars**.

    Two independent computation paths run on the same dataset:

    - **Pandas**: daily score trend (resample by day) + 7-evaluation rolling
      average — ideal for time-series with datetime index operations.
    - **Polars**: severity distribution (%) + workflow failure rate — ideal for
      fast columnar group-by aggregations with a functional/immutable API.

    Returns an `AnalyticsReport` with both results merged together.
    """
    raw_rows = store.get_raw_rows()
    return build_analytics_report(raw_rows)
