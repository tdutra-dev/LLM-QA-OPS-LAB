"""
Step 8 — AgentLoop: the autonomous percezione → valutazione → azione cycle.

Architecture
────────────
The AgentLoop is the top-level orchestrator that ties every previous step
together into a self-running agentic system:

    ┌─────────────────────────────────────────────────────────────┐
    │                        Agent Loop                           │
    │                                                             │
    │  every <interval> seconds:                                  │
    │                                                             │
    │  1. PERCEIVE    incident_generator.generate()               │
    │                 → EvaluationRequest                         │
    │                                                             │
    │  2. EVALUATE    engine.evaluate(request)                    │
    │                 → EvaluationResult (status, score, action)  │
    │                                                             │
    │  3. STORE       store.save(EvaluationRecord)                │
    │                 → PostgreSQL evaluation_records             │
    │                                                             │
    │  4. ACT         action_executor.execute(record)             │
    │                 → ActionLog (or None if status='ok')        │
    │                                                             │
    │  5. AUDIT       store.save_action(action_log)               │
    │                 → PostgreSQL action_logs                    │
    └─────────────────────────────────────────────────────────────┘

Design decisions
────────────────
- **AsyncIO, not threads**: the loop runs as an `asyncio.Task` in FastAPI's
  event loop. DB calls are dispatched to a thread-pool via `asyncio.to_thread`
  so the event loop is never blocked.

- **Singleton pattern**: `_loop` module-level instance keeps a single agent
  alive for the lifetime of the process. FastAPI endpoints call
  `get_agent_loop()` to obtain it.

- **Graceful stop**: `stop()` cancels the task and awaits its completion,
  ensuring any in-progress cycle finishes cleanly.

- **Idempotent start**: calling `start()` while the loop is already running
  returns the current status without creating a second loop.

- **Redis invalidation**: after every cycle that persisted a record, the
  metrics and analytics caches are invalidated — identical to the behaviour
  of `POST /evaluate`.

Extending for production
─────────────────────────
To consume a real incident queue, replace `incident_generator.generate()`
with an async call to your queue library (aiobotocore for SQS, aiokafka,
asyncpg LISTEN for PostgreSQL, etc.).  The rest of the loop is unchanged.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from . import redis_cache
from .action_executor import execute as execute_action
from .database import SessionLocal
from .engine import evaluate
from .incident_generator import generate as generate_incident
from .models import AgentStatus, EvaluationRecord
from .redis_cache import KEY_ANALYTICS, KEY_METRICS
from .store import IncidentStore

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Autonomous percezione → valutazione → azione cycle.

    Lifecycle
    ---------
    await loop.start(interval_s=5.0)   # spin up
    loop.status()                      # inspect at any time
    await loop.stop()                  # shut down cleanly
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._cycles: int = 0
        self._actions_executed: int = 0
        self._started_at: datetime | None = None
        self._last_cycle_at: datetime | None = None
        self._interval_s: float | None = None

    # ── Public interface ───────────────────────────────────────────────────────

    async def start(self, interval_s: float = 5.0) -> AgentStatus:
        """
        Start the autonomous loop with the given polling interval.

        Idempotent: returns current status if the loop is already running.
        """
        if self._running and self._task and not self._task.done():
            logger.info("[agent] already running — ignoring duplicate start()")
            return self.status()

        self._running = True
        self._cycles = 0
        self._actions_executed = 0
        self._started_at = datetime.now(timezone.utc)
        self._last_cycle_at = None
        self._interval_s = interval_s

        self._task = asyncio.create_task(
            self._run_loop(interval_s),
            name="agent-loop",
        )
        logger.info("[agent] started with interval=%.1f s", interval_s)
        return self.status()

    async def stop(self) -> AgentStatus:
        """
        Stop the loop and wait for the current cycle to finish.

        Idempotent: safe to call when the loop is not running.
        """
        if not self._running:
            logger.info("[agent] stop() called but loop not running — no-op")
            return self.status()

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass  # expected
        self._task = None
        logger.info(
            "[agent] stopped after %d cycles, %d actions executed",
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

    # ── Internal loop ──────────────────────────────────────────────────────────

    async def _run_loop(self, interval_s: float) -> None:
        """Main asyncio loop — runs until cancelled."""
        logger.info("[agent] loop task started (interval=%.1f s)", interval_s)
        while self._running:
            try:
                # Run the blocking cycle in a thread so asyncio event loop is free
                actions = await asyncio.to_thread(self._run_one_cycle)
                self._cycles += 1
                self._actions_executed += actions
                self._last_cycle_at = datetime.now(timezone.utc)

                logger.info(
                    "[agent] cycle=%d actions=%d total_actions=%d",
                    self._cycles, actions, self._actions_executed,
                )
            except asyncio.CancelledError:
                raise  # let the cancellation propagate cleanly
            except Exception:
                logger.exception("[agent] unhandled error in cycle %d — continuing", self._cycles + 1)

            try:
                await asyncio.sleep(interval_s)
            except asyncio.CancelledError:
                raise

    def _run_one_cycle(self) -> int:
        """
        Execute one full percezione → valutazione → azione cycle.

        Runs in a thread-pool worker (called via `asyncio.to_thread`).
        Opens its own SQLAlchemy session and closes it when done.

        Returns
        -------
        int
            Number of autonomous actions executed this cycle (0 or 1).
        """
        # 1. PERCEIVE ──────────────────────────────────────────────────────────
        request = generate_incident()
        logger.debug(
            "[agent:perceive] workflow=%s type=%s severity=%s",
            request.incident.workflow,
            request.incident.incidentType,
            request.incident.severity,
        )

        # 2. EVALUATE ──────────────────────────────────────────────────────────
        result = evaluate(request)
        logger.debug("[agent:evaluate] status=%s score=%d action=%s",
                     result.status, result.score, result.suggestedAction)

        # 3. ASSEMBLE record + STORE ───────────────────────────────────────────
        record = EvaluationRecord(
            recordId=f"rec_{uuid4().hex[:8]}",
            receivedAt=datetime.now(timezone.utc).isoformat(),
            incident=request.incident,
            result=result,
        )

        db = SessionLocal()
        actions_this_cycle = 0
        try:
            store = IncidentStore(db)
            store.save(record)

            # Invalidate caches — same as POST /evaluate
            redis_cache.invalidate(KEY_METRICS, KEY_ANALYTICS)

            # 4. ACT ───────────────────────────────────────────────────────────
            action_log = execute_action(record)

            # 5. AUDIT ─────────────────────────────────────────────────────────
            if action_log is not None:
                store.save_action(action_log)
                actions_this_cycle = 1
                logger.info(
                    "[agent:act] %s → %s | %s",
                    action_log.actionType,
                    action_log.outcome,
                    action_log.detail[:80],
                )
        finally:
            db.close()

        return actions_this_cycle


# ── Module-level singleton ─────────────────────────────────────────────────────

_loop = AgentLoop()


def get_agent_loop() -> AgentLoop:
    """Return the module-level singleton AgentLoop instance."""
    return _loop
