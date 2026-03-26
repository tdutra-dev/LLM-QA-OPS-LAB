from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Query

from .database import Base, engine, SessionLocal
from .analytics import build_analytics_report
from .action_executor import execute as execute_action
from .agent_loop import get_agent_loop
from .engine import evaluate
from . import redis_cache
from .redis_cache import KEY_ANALYTICS, KEY_METRICS
from .models import (
    ActionLog,
    AgentStatus,
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
    print(f"[startup] Redis cache available: {redis_cache.is_available()}")
    yield
    print("[shutdown] evaluation service stopped")


app = FastAPI(
    title="LLM-QA-OPS Evaluation Service",
    version="0.7.0",
    description=(
        "Evaluates LLM pipeline incidents and autonomously executes remediation actions. "
        "Includes an autonomous Agent Loop (percezione → valutazione → azione). "
        "Part of the LLM-QA-OPS-LAB roadmap — Step 8: Agent Loop."
    ),
    lifespan=lifespan,
)


# ── Background task ───────────────────────────────────────────────────────────

def _persist_record(record: EvaluationRecord) -> None:
    """
    Background task: persist the evaluation record to PostgreSQL and then
    let the ActionExecutor decide what autonomous remediation to apply.

    Runs AFTER the HTTP response has already been sent to the client.
    We open a fresh Session here (not via Depends) because background tasks
    run outside FastAPI's per-request dependency lifecycle.
    """
    print(
        f"[bg] record saved | id={record.recordId}"
        f" | workflow={record.incident.workflow}"
        f" | status={record.result.status}"
        f" | score={record.result.score}"
    )
    # ActionExecutor: dispatch and persist the autonomous action
    action_log = execute_action(record)
    if action_log is not None:
        db = SessionLocal()
        try:
            store = IncidentStore(db)
            store.save_action(action_log)
        finally:
            db.close()
        print(
            f"[action] {action_log.actionType} → {action_log.outcome}"
            f" | {action_log.detail[:80]}"
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    """Liveness probe — includes Redis status."""
    return {"status": "ok", "redis": "up" if redis_cache.is_available() else "down"}


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

    # Invalidate cached metrics/analytics so next read reflects this new record.
    # Must happen BEFORE the background task so the cache is stale-free.
    redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)

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

    Response is cached in Redis for 30 s (cache-aside pattern).
    Cache is invalidated on every POST /evaluate.
    """
    cached = redis_cache.get(KEY_METRICS)
    if cached is not None:
        return MetricsSummary.model_validate(cached)

    result = store.get_metrics()
    redis_cache.set(KEY_METRICS, result.model_dump())
    return result


@app.get("/actions", response_model=list[ActionLog], tags=["Actions"])
def list_actions(
    workflow: str | None = Query(default=None, description="Filter by workflow name"),
    action_type: str | None = Query(
        default=None,
        description="Filter by action type: monitor | retry | inspect_prompt | inspect_schema | check_provider | escalate",
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Max records to return (newest first)"),
    store: IncidentStore = Depends(get_store),
) -> list[ActionLog]:
    """
    List autonomous action logs produced by the ActionExecutor.

    Each entry records what action was taken after an incident evaluation,
    allowing operators to audit the system's autonomous decisions.
    Supports optional filtering by workflow name and action type.
    """
    return store.get_actions(workflow=workflow, action_type=action_type, limit=limit)


# ── Agent Loop control endpoints ───────────────────────────────────────────────

@app.post("/agent/start", response_model=AgentStatus, tags=["Agent"])
async def agent_start(
    interval: float = Query(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Polling interval in seconds (1–60). How often the loop runs one percezione→valutazione→azione cycle.",
    ),
) -> AgentStatus:
    """
    Start the autonomous Agent Loop.

    The loop runs a full percezione → valutazione → azione cycle every
    `interval` seconds:
    1. **Perceive** — `incident_generator.generate()` produces a synthetic incident
    2. **Evaluate** — the LLM evaluation engine scores it
    3. **Store** — the EvaluationRecord is persisted to PostgreSQL
    4. **Act** — the ActionExecutor dispatches the remediation handler
    5. **Audit** — the ActionLog is persisted to PostgreSQL

    Idempotent: if the loop is already running, returns current status.
    """
    return await get_agent_loop().start(interval_s=interval)


@app.post("/agent/stop", response_model=AgentStatus, tags=["Agent"])
async def agent_stop() -> AgentStatus:
    """
    Stop the autonomous Agent Loop gracefully.

    Waits for the current cycle to complete before stopping.
    Idempotent: safe to call when the loop is not running.
    """
    return await get_agent_loop().stop()


@app.get("/agent/status", response_model=AgentStatus, tags=["Agent"])
def agent_status() -> AgentStatus:
    """
    Return the current status of the autonomous Agent Loop.

    Includes: running state, cycles completed, actions executed,
    start time, last cycle time, and polling interval.
    """
    return get_agent_loop().status()


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

    Response is cached in Redis for 30 s (cache-aside pattern).
    Cache is invalidated on every POST /evaluate.
    """
    cached = redis_cache.get(KEY_ANALYTICS)
    if cached is not None:
        return AnalyticsReport.model_validate(cached)

    raw_rows = store.get_raw_rows()
    result = build_analytics_report(raw_rows)
    redis_cache.set(KEY_ANALYTICS, result.model_dump())
    return result
