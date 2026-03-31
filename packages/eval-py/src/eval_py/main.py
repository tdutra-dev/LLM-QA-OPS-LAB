from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Query

from .database import Base, engine, SessionLocal
from .analytics import build_analytics_report
from .action_executor import execute as execute_action
from .agent_loop import get_agent_loop
from .langgraph_agent import get_langgraph_loop, run_one_cycle, get_compiled_graph
from .engine import evaluate
from .tool_calling import evaluate_with_tools
from . import metrics as m
from . import redis_cache
from .redis_cache import KEY_ANALYTICS, KEY_METRICS
from .rag_retriever import find_similar_incidents, build_rag_context
from .models import (
    ActionLog,
    AgentStatus,
    AnalyticsReport,
    EvaluationRecord,
    EvaluationRequest,
    EvaluationResult,
    MetricsSummary,
    RagEvaluationResult,
    SimilarIncidentResponse,
    ToolCallLog,
    ToolCallingEvaluationResult,
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
    from sqlalchemy import text as sql_text

    # Step 12: enable the pgvector extension before creating tables.
    # This is idempotent — safe to run on every startup.
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        print("[startup] pgvector extension ready")
    except Exception as exc:
        print(f"[startup] pgvector extension not available ({exc}) — RAG disabled")

    Base.metadata.create_all(bind=engine)
    print("[startup] PostgreSQL tables ready")
    print(f"[startup] Redis cache available: {redis_cache.is_available()}")
    print(f"[startup] Prometheus metrics available: {m.is_available()}")
    yield
    print("[shutdown] evaluation service stopped")


app = FastAPI(
    title="LLM-QA-OPS Evaluation Service",
    version="0.12.0",
    description=(
        "Evaluates LLM pipeline incidents and autonomously executes remediation actions. "
        "Step 12: RAG-enhanced evaluation with pgvector + Prometheus observability."
    ),
    lifespan=lifespan,
)

# ── Step 12: Prometheus instrumentation ──────────────────────────────────
# Instruments all endpoints automatically (request count + duration histograms)
# and exposes the /prometheus-metrics endpoint for Prometheus scraping.
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/prometheus-metrics")
except ImportError:
    pass  # Graceful degradation: service runs without metrics if pkg not installed


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

    # Step 12: track Prometheus metrics
    m.eval_requests_total.labels(status=result.status).inc()
    m.eval_score_histogram.observe(result.score)

    # Invalidate cached metrics/analytics so next read reflects this new record.
    # Must happen BEFORE the background task so the cache is stale-free.
    redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)

    # Schedule persistence AFTER the response is sent — non-blocking
    background_tasks.add_task(_persist_record, record)

    return result


@app.post("/evaluate/tool-call", response_model=ToolCallingEvaluationResult, tags=["Evaluation"])
def evaluate_tool_call_endpoint(
    req: EvaluationRequest,
    background_tasks: BackgroundTasks,
    store: IncidentStore = Depends(get_store),
) -> ToolCallingEvaluationResult:
    """
    Evaluate a single incident using LLM-driven tool calling.

    Instead of deterministic rule-based evaluation, this endpoint uses
    OpenAI function calling to let the LLM choose which remediation
    tools to invoke and with what arguments.

    The LLM analyzes the incident context and can select multiple tools
    (escalate + monitor, retry with specific strategy, etc.) based on
    sophisticated reasoning about the incident details.

    Requires OPENAI_API_KEY in environment variables.
    """
    # LLM-driven evaluation and tool selection
    result = evaluate_with_tools(req)
    
    # Create audit records for both the evaluation and tool usage
    record = EvaluationRecord(
        recordId=f"rec_{uuid4().hex[:8]}",
        receivedAt=datetime.now(timezone.utc).isoformat(),
        incident=req.incident,
        # Convert tool calling result to standard result format for storage
        result=EvaluationResult(
            status=result.status,
            score=result.score,
            summary=result.summary,
            reasoning=result.reasoning,
            suggestedAction=None,  # Tool calling doesn't use suggestedAction
            tags=result.tags,
        ),
    )
    
    # Save the evaluation record
    store.save(record)
    
    # Create tool call audit log
    if result.toolCalls:
        tool_log = ToolCallLog(
            logId=f"tlog_{uuid4().hex[:8]}",
            recordId=record.recordId,
            executedAt=datetime.now(timezone.utc).isoformat(),
            llmModel="gpt-4o-mini",
            toolCallsJson=str([tc.model_dump() for tc in result.toolCalls]),
            totalTools=len(result.toolCalls),
            successfulTools=len([r for r in result.toolResults if r.outcome == "success"]),
            workflow=req.incident.workflow,
            severity=req.incident.severity,
        )
        store.save_tool_call_log(tool_log)
    
    # Invalidate caches
    redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)
    
    # Background persistence (same as regular /evaluate)
    background_tasks.add_task(_persist_record, record)
    
    return result


# ── Step 12: RAG-augmented evaluation endpoint ────────────────────────────────

@app.post("/evaluate/rag", response_model=RagEvaluationResult, tags=["Evaluation"])
def evaluate_rag_endpoint(
    req: EvaluationRequest,
    background_tasks: BackgroundTasks,
    top_k: int = Query(default=3, ge=1, le=10, description="Number of similar past incidents to retrieve"),
    store: IncidentStore = Depends(get_store),
) -> RagEvaluationResult:
    """
    RAG-augmented incident evaluation using pgvector similarity search.

    **How it works:**

    1. **Embed** the incoming incident into a 1536-dim vector (OpenAI text-embedding-3-small)
    2. **Retrieve** the top-K most semantically similar past incidents from PostgreSQL
       using the pgvector cosine distance operator (`<=>`)
    3. **Evaluate** the incident with the standard rule-based engine
    4. **Augment** the response with the retrieved historical context
    5. **Store** the new record + persist its embedding for future retrieval

    The `similarIncidents` field in the response gives operators full visibility
    into which historical cases were used as context, and how similar they were.

    **Graceful degradation:** if embeddings are unavailable (no OPENAI_API_KEY,
    pgvector not installed, or no historical data yet), falls back to standard
    evaluation with `ragContextUsed=false`.

    Requires OPENAI_API_KEY for embedding generation.
    """
    import time

    # 1. Retrieve similar incidents via pgvector
    t0 = time.perf_counter()
    similar = find_similar_incidents(
        incident_json=req.incident.model_dump(),
        db=store.db,
        top_k=top_k,
    )
    retrieval_latency = time.perf_counter() - t0

    # Step 12: track RAG retrieval metrics
    m.rag_retrieval_latency.observe(retrieval_latency)
    m.rag_similar_found.observe(len(similar))
    m.rag_requests_total.labels(retrieval="hit" if similar else "miss").inc()

    # 2. Run standard rule-based evaluation
    base_result = evaluate(req)

    # Step 12: track evaluation metrics
    m.eval_requests_total.labels(status=base_result.status).inc()
    m.eval_score_histogram.observe(base_result.score)

    # 3. Build enriched response
    embedding_stored = False
    record = EvaluationRecord(
        recordId=f"rec_{uuid4().hex[:8]}",
        receivedAt=datetime.now(timezone.utc).isoformat(),
        incident=req.incident,
        result=base_result,
    )
    store.save(record)  # also stores the embedding (best-effort, inside save())
    # Check if embedding was stored (pgvector available + OPENAI_API_KEY set)
    try:
        from .rag_retriever import generate_embedding
        embedding_stored = generate_embedding("test") is not None
    except Exception:
        pass

    redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)
    background_tasks.add_task(_persist_record, record)

    rag_context = build_rag_context(similar)

    return RagEvaluationResult(
        # Base evaluation fields
        status=base_result.status,
        score=base_result.score,
        summary=base_result.summary,
        reasoning=(
            base_result.reasoning + "\n\n" + rag_context
            if rag_context and base_result.reasoning
            else base_result.reasoning or rag_context or ""
        ),
        suggestedAction=base_result.suggestedAction,
        tags=base_result.tags,
        # RAG-specific fields
        similarIncidents=[
            SimilarIncidentResponse(
                recordId=s.record_id,
                workflow=s.workflow,
                incidentType=s.incident_type,
                severity=s.severity,
                summary=s.summary,
                suggestedAction=s.suggested_action,
                evalStatus=s.eval_status,
                evalScore=s.eval_score,
                similarity=s.similarity,
            )
            for s in similar
        ],
        ragContextUsed=len(similar) > 0,
        embeddingStored=embedding_stored,
    )


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


# ── LangGraph Agent endpoints (Step 14) ──────────────────────────────────────

@app.get("/agent/graph/topology", tags=["LangGraph"])
def agent_graph_topology() -> dict:
    """
    Return the Mermaid diagram of the compiled LangGraph pipeline.

    Paste the ``mermaid`` value at https://mermaid.live to visualise
    the full perceive → retrieve_context → evaluate → store → act → audit graph.
    """
    mermaid = get_compiled_graph().get_graph().draw_mermaid()
    return {"mermaid": mermaid}


@app.post("/agent/graph/run", tags=["LangGraph"])
def agent_graph_run_cycle() -> dict:
    """
    Execute **one** LangGraph pipeline cycle synchronously and return a summary.

    Pipeline: perceive → retrieve_context (RAG) → evaluate → store → act → [audit]

    Useful for manual testing, demo, and CI smoke tests.
    Returns the cycle_id, record_id, eval status/score, action taken, and RAG hit count.
    """
    state = run_one_cycle()
    record = state.get("record")
    result = state.get("result")
    action_log = state.get("action_log")
    return {
        "cycle_id": state["cycle_id"],
        "rag_similar_found": state.get("similar_count", 0),
        "record_id": record.recordId if record else None,
        "eval_status": result.status if result else None,
        "eval_score": result.score if result else None,
        "suggested_action": result.suggestedAction if result else None,
        "action_executed": action_log.actionType if action_log else None,
        "action_outcome": action_log.outcome if action_log else None,
    }


@app.post("/agent/graph/start", response_model=AgentStatus, tags=["LangGraph"])
async def agent_graph_start(
    interval: float = Query(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Polling interval in seconds (1–60).",
    ),
) -> AgentStatus:
    """
    Start the **LangGraph-backed** autonomous agent loop.

    Identical behaviour to ``POST /agent/start`` but the pipeline runs through
    the typed LangGraph StateGraph with RAG context retrieval before evaluation.
    Idempotent: returns current status if already running.
    """
    return await get_langgraph_loop().start(interval_s=interval)


@app.post("/agent/graph/stop", response_model=AgentStatus, tags=["LangGraph"])
async def agent_graph_stop() -> AgentStatus:
    """Stop the LangGraph agent loop gracefully."""
    return await get_langgraph_loop().stop()


@app.get("/agent/graph/status", response_model=AgentStatus, tags=["LangGraph"])
def agent_graph_status() -> AgentStatus:
    """Return the current status of the LangGraph agent loop."""
    return get_langgraph_loop().status()


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
