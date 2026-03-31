"""
Step 14 — LangGraph Agent: RAG-augmented agentic pipeline.

Architecture
────────────
Reimplements the perceive → evaluate → act cycle (Step 8) as a typed
LangGraph StateGraph.  Each step becomes an explicit graph node; state
is a TypedDict that flows through the pipeline with full type safety.

The key upgrade over the plain AgentLoop is the ``retrieve_context`` node,
which injects semantically similar past incidents (pgvector RAG) **before**
the evaluate step — grounding the decision in historical precedent.

    ┌──────────────────────────────────────────────────────────────────┐
    │                    LangGraph Agent Pipeline                      │
    │                                                                  │
    │  START                                                           │
    │    │                                                             │
    │    ▼                                                             │
    │  [perceive]         generate_incident() → EvaluationRequest      │
    │    │                                                             │
    │    ▼                                                             │
    │  [retrieve_context] pgvector cosine search → RAG context string  │
    │    │                                                             │
    │    ▼                                                             │
    │  [evaluate]         engine.evaluate(request) → EvaluationResult  │
    │    │                                                             │
    │    ▼                                                             │
    │  [store]            persist EvaluationRecord + invalidate cache  │
    │    │                                                             │
    │    ▼                                                             │
    │  [act]              execute_action(record) → ActionLog | None    │
    │    │                                                             │
    │    ├─── action_log != None ──► [audit]  persist ActionLog        │
    │    │                              │                              │
    │    └─── action_log == None ──────►│                              │
    │                                   ▼                              │
    │                                  END                             │
    └──────────────────────────────────────────────────────────────────┘

Design decisions
────────────────
- **LangGraph StateGraph**: explicit typed state (TypedDict) instead of
  implicit local variables.  Every node receives the full state and returns
  only the keys it updates — standard LangGraph reducer pattern.

- **RAG-augmented evaluate**: ``retrieve_context`` runs pgvector similarity
  search before evaluation, attaching ``rag_context`` and ``similar_count``
  to state.  The evaluate node logs this context; future iterations can feed
  it into an LLM prompt for context-aware scoring.

- **MemorySaver checkpointer**: state is persisted after every node, enabling
  inspection, replay, and future streaming via LangGraph's built-in API.

- **Drop-in interface**: ``LangGraphAgentLoop`` exposes the same
  ``start() / stop() / status()`` API as the original ``AgentLoop``, so
  FastAPI endpoints need minimal changes.

- **Backward compatibility**: original ``AgentLoop`` is untouched.
  Both implementations co-exist; the router can switch between them.

Extending for production
─────────────────────────
To add a context-enriched LLM evaluation, modify ``evaluate_node`` to
pass ``state["rag_context"]`` into the prompt alongside the incident.
The node boundary makes this change isolated and testable.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from . import redis_cache
from .action_executor import execute as execute_action
from .database import SessionLocal
from .engine import evaluate
from .incident_generator import generate as generate_incident
from .models import ActionLog, AgentStatus, EvaluationRecord, EvaluationRequest, EvaluationResult
from .rag_retriever import SimilarIncident, build_rag_context, find_similar_incidents
from .redis_cache import KEY_ANALYTICS, KEY_METRICS
from .store import IncidentStore

logger = logging.getLogger(__name__)


# ── Typed State ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    Immutable state snapshot flowing through the LangGraph pipeline.

    Each node receives the full state and returns a partial dict with
    only the keys it modifies — LangGraph merges them via reducers.
    """
    cycle_id: str
    # Node: perceive
    request: Optional[EvaluationRequest]
    # Node: retrieve_context
    rag_context: str
    similar_count: int
    # Node: evaluate
    result: Optional[EvaluationResult]
    # Node: store
    record: Optional[EvaluationRecord]
    # Node: act / audit
    action_log: Optional[ActionLog]


# ── Graph Nodes ───────────────────────────────────────────────────────────────

def perceive_node(state: AgentState) -> dict:
    """
    PERCEIVE — generate a new incident to evaluate.

    In production: replace ``generate_incident()`` with an async queue
    consumer (SQS, Kafka, PostgreSQL LISTEN, etc.).
    """
    request = generate_incident()
    logger.debug(
        "[lg:perceive] cycle=%s  workflow=%s  type=%s  severity=%s",
        state["cycle_id"],
        request.incident.workflow,
        request.incident.incidentType,
        request.incident.severity,
    )
    return {"request": request}


def retrieve_context_node(state: AgentState) -> dict:
    """
    RETRIEVE CONTEXT — pgvector RAG: find semantically similar past incidents.

    Converts the new incident to text → embeds with text-embedding-3-small →
    cosine similarity search in PostgreSQL → formats as LLM-ready context.

    Gracefully degrades to empty context if OpenAI key is absent or DB
    has no embeddings yet (first run).
    """
    request = state["request"]
    if request is None:
        return {"rag_context": "", "similar_count": 0}

    incident_dict = request.incident.model_dump()
    db = SessionLocal()
    try:
        similar: list[SimilarIncident] = find_similar_incidents(
            incident_dict, db, top_k=3
        )
        context = build_rag_context(similar)
        logger.debug(
            "[lg:retrieve_context] cycle=%s  similar_found=%d",
            state["cycle_id"], len(similar),
        )
        return {"rag_context": context, "similar_count": len(similar)}
    finally:
        db.close()


def evaluate_node(state: AgentState) -> dict:
    """
    EVALUATE — score the incident and suggest a remediation action.

    The ``rag_context`` from the previous node is available in state for
    future prompt injection (context-enriched LLM scoring).
    """
    request = state["request"]
    if request is None:
        raise ValueError("[lg:evaluate] request is None — perceive node failed")

    result = evaluate(request)

    if state["rag_context"]:
        logger.debug(
            "[lg:evaluate] cycle=%s  status=%s  score=%d  action=%s  "
            "rag_context_chars=%d",
            state["cycle_id"], result.status, result.score,
            result.suggestedAction, len(state["rag_context"]),
        )
    else:
        logger.debug(
            "[lg:evaluate] cycle=%s  status=%s  score=%d  action=%s  (no rag context)",
            state["cycle_id"], result.status, result.score, result.suggestedAction,
        )

    return {"result": result}


def store_node(state: AgentState) -> dict:
    """
    STORE — persist the EvaluationRecord to PostgreSQL + invalidate Redis cache.
    """
    request = state["request"]
    result = state["result"]
    if request is None or result is None:
        raise ValueError("[lg:store] request or result is None")

    record = EvaluationRecord(
        recordId=f"rec_{uuid4().hex[:8]}",
        receivedAt=datetime.now(timezone.utc).isoformat(),
        incident=request.incident,
        result=result,
    )

    db = SessionLocal()
    try:
        store = IncidentStore(db)
        store.save(record)
        redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)
        logger.debug("[lg:store] cycle=%s  record_id=%s", state["cycle_id"], record.recordId)
        return {"record": record}
    finally:
        db.close()


def act_node(state: AgentState) -> dict:
    """
    ACT — execute the suggested remediation action autonomously.

    Returns ``action_log=None`` when the incident status is 'ok' (no action
    needed); the conditional edge routes to END in that case.
    """
    record = state["record"]
    if record is None:
        raise ValueError("[lg:act] record is None — store node failed")

    action_log = execute_action(record)
    if action_log is not None:
        logger.info(
            "[lg:act] cycle=%s  type=%s  outcome=%s  detail=%s",
            state["cycle_id"],
            action_log.actionType,
            action_log.outcome,
            action_log.detail[:80],
        )
    else:
        logger.debug("[lg:act] cycle=%s  no action required", state["cycle_id"])

    return {"action_log": action_log}


def audit_node(state: AgentState) -> dict:
    """
    AUDIT — persist the ActionLog to PostgreSQL for full decision traceability.

    Only reached when act_node produced a non-None action_log.
    """
    action_log = state["action_log"]
    if action_log is None:
        return {}

    db = SessionLocal()
    try:
        store = IncidentStore(db)
        store.save_action(action_log)
        logger.debug(
            "[lg:audit] cycle=%s  action_id=%s  persisted",
            state["cycle_id"],
            action_log.actionId,
        )
        return {}
    finally:
        db.close()


# ── Conditional Routing ───────────────────────────────────────────────────────

def route_after_act(state: AgentState) -> str:
    """
    Conditional edge: route to 'audit' if an action was executed, else END.

    This is the branching logic that makes the graph non-linear.
    """
    return "audit" if state.get("action_log") is not None else END


# ── Graph Construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and return the uncompiled StateGraph.

    Useful for visualization:
        graph = build_graph()
        compiled = graph.compile()
        print(compiled.get_graph().draw_mermaid())
    """
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("perceive", perceive_node)
    g.add_node("retrieve_context", retrieve_context_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("store", store_node)
    g.add_node("act", act_node)
    g.add_node("audit", audit_node)

    # Linear edges
    g.set_entry_point("perceive")
    g.add_edge("perceive", "retrieve_context")
    g.add_edge("retrieve_context", "evaluate")
    g.add_edge("evaluate", "store")
    g.add_edge("store", "act")

    # Conditional edge after act
    g.add_conditional_edges(
        "act",
        route_after_act,
        {"audit": "audit", END: END},
    )
    g.add_edge("audit", END)

    return g


def compile_graph(checkpointer=None):
    """
    Compile the graph with an optional checkpointer.

    Default: MemorySaver (in-process, suitable for single-instance deployment).
    For multi-replica production: use langgraph.checkpoint.postgres.PostgresSaver.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_graph().compile(checkpointer=checkpointer)


# Module-level compiled graph (shared across requests)
_compiled_graph = compile_graph()


def get_compiled_graph():
    """Return the module-level compiled graph."""
    return _compiled_graph


# ── Single-cycle runner ───────────────────────────────────────────────────────

def run_one_cycle(cycle_id: str | None = None) -> AgentState:
    """
    Execute one full perceive → retrieve → evaluate → store → act → audit cycle.

    Returns the final AgentState after all nodes have run.
    Suitable for direct invocation from tests or a background task.
    """
    if cycle_id is None:
        cycle_id = f"cycle_{uuid4().hex[:8]}"

    initial_state: AgentState = {
        "cycle_id": cycle_id,
        "request": None,
        "rag_context": "",
        "similar_count": 0,
        "result": None,
        "record": None,
        "action_log": None,
    }

    config = {"configurable": {"thread_id": cycle_id}}
    final_state = _compiled_graph.invoke(initial_state, config=config)
    return final_state


# ── LangGraphAgentLoop ────────────────────────────────────────────────────────

class LangGraphAgentLoop:
    """
    Drop-in replacement for AgentLoop (Step 8) backed by the LangGraph pipeline.

    Exposes the same start() / stop() / status() interface so FastAPI
    endpoints require zero changes to switch implementations.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._cycles: int = 0
        self._actions_executed: int = 0
        self._started_at: datetime | None = None
        self._last_cycle_at: datetime | None = None
        self._interval_s: float | None = None

    async def start(self, interval_s: float = 5.0) -> AgentStatus:
        """Start the LangGraph-backed autonomous loop."""
        if self._running and self._task and not self._task.done():
            logger.info("[lg-loop] already running — ignoring duplicate start()")
            return self.status()

        self._running = True
        self._cycles = 0
        self._actions_executed = 0
        self._started_at = datetime.now(timezone.utc)
        self._last_cycle_at = None
        self._interval_s = interval_s

        self._task = asyncio.create_task(
            self._run_loop(interval_s),
            name="langgraph-agent-loop",
        )
        logger.info("[lg-loop] started with interval=%.1f s (LangGraph pipeline)", interval_s)
        return self.status()

    async def stop(self) -> AgentStatus:
        """Stop the loop and wait for the current cycle to finish."""
        if not self._running:
            return self.status()

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info(
            "[lg-loop] stopped after %d cycles, %d actions executed",
            self._cycles, self._actions_executed,
        )
        return self.status()

    def status(self) -> AgentStatus:
        """Return the current agent status snapshot."""
        return AgentStatus(
            running=self._running and bool(self._task and not self._task.done()),
            cyclesCompleted=self._cycles,
            actionsExecuted=self._actions_executed,
            startedAt=self._started_at.isoformat() if self._started_at else None,
            lastCycleAt=self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            intervalSeconds=self._interval_s,
        )

    async def _run_loop(self, interval_s: float) -> None:
        """Main asyncio loop — runs LangGraph cycles until cancelled."""
        while self._running:
            try:
                final_state: AgentState = await asyncio.to_thread(
                    run_one_cycle,
                    f"cycle_{self._cycles + 1}",
                )
                self._cycles += 1
                actions = 1 if final_state.get("action_log") is not None else 0
                self._actions_executed += actions
                self._last_cycle_at = datetime.now(timezone.utc)
                logger.info(
                    "[lg-loop] cycle=%d  record=%s  action=%s  rag_similar=%d",
                    self._cycles,
                    final_state.get("record", {}).recordId if final_state.get("record") else "—",
                    final_state.get("action_log", {}).actionType if final_state.get("action_log") else "none",
                    final_state.get("similar_count", 0),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[lg-loop] unhandled error in cycle %d — continuing", self._cycles + 1)

            try:
                await asyncio.sleep(interval_s)
            except asyncio.CancelledError:
                raise


# ── Module-level singleton ────────────────────────────────────────────────────

_lg_loop = LangGraphAgentLoop()


def get_langgraph_loop() -> LangGraphAgentLoop:
    """Return the module-level LangGraphAgentLoop singleton."""
    return _lg_loop
