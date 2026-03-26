"""
PostgreSQL-backed IncidentStore — Step 3 replacement for the in-memory store.

The Depends(get_store) pattern in main.py is unchanged.
Only this file changed: from list → SQLAlchemy Session.

That is the direct benefit of the Dependency Injection pattern we set up
in Step 2: the endpoints are completely unaware of how storage works.
"""
from __future__ import annotations

from collections import Counter

from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_db
from .db_models import ActionLogORM, IncidentRecordORM, ToolCallLogORM
from .models import (
    ActionCount,
    ActionLog,
    EvaluationRecord,
    EvaluationResult,
    MetricsSummary,
    StandardIncident,
    StatusCount,
    ToolCallLog,
)


class IncidentStore:
    def __init__(self, db: Session) -> None:
        # The Session is injected by FastAPI via Depends(get_db)
        # — one session per HTTP request, closed automatically after.
        self.db = db

    # ── writes ────────────────────────────────────────────────────────────────

    def save(self, record: EvaluationRecord) -> None:
        """Persist an EvaluationRecord to PostgreSQL."""
        orm = IncidentRecordORM(
            record_id=record.recordId,
            workflow=record.incident.workflow,
            incident_type=record.incident.incidentType,
            severity=record.incident.severity,
            eval_status=record.result.status,
            eval_score=record.result.score,
            suggested_action=record.result.suggestedAction,
            summary=record.result.summary,
            # Store full payloads as JSONB for reconstruction + future analytics
            incident_json=record.incident.model_dump(),
            result_json=record.result.model_dump(),
        )
        self.db.add(orm)
        self.db.commit()

    def save_action(self, action_log: ActionLog) -> None:
        """Persist an ActionLog to the action_logs table."""
        orm = ActionLogORM(
            action_id=action_log.actionId,
            record_id=action_log.recordId,
            executed_at=action_log.executedAt,
            action_type=action_log.actionType,
            outcome=action_log.outcome,
            detail=action_log.detail,
            workflow=action_log.workflow,
            severity=action_log.severity,
        )
        self.db.add(orm)
        self.db.commit()

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_actions(
        self,
        workflow: str | None = None,
        action_type: str | None = None,
        limit: int = 50,
    ) -> list[ActionLog]:
        """Query action_logs with optional filters, newest first."""
        query = self.db.query(ActionLogORM)

        if workflow:
            query = query.filter(ActionLogORM.workflow == workflow)
        if action_type:
            query = query.filter(ActionLogORM.action_type == action_type)

        rows = query.order_by(ActionLogORM.id.desc()).limit(limit).all()
        return [
            ActionLog(
                actionId=r.action_id,
                recordId=r.record_id,
                executedAt=str(r.executed_at),
                actionType=r.action_type,  # type: ignore[arg-type]
                outcome=r.outcome,          # type: ignore[arg-type]
                detail=r.detail,
                workflow=r.workflow,
                severity=r.severity,
            )
            for r in rows
        ]

    def save_tool_call_log(self, log: ToolCallLog) -> None:
        """Persist a ToolCallLog to the tool_call_logs table."""
        orm = ToolCallLogORM(
            log_id=log.logId,
            record_id=log.recordId,
            executed_at=log.executedAt,
            llm_model=log.llmModel,
            tool_calls_json=log.toolCallsJson,
            total_tools=log.totalTools,
            successful_tools=log.successfulTools,
            workflow=log.workflow,
            severity=log.severity,
        )
        self.db.add(orm)
        self.db.commit()

    def get_tool_call_logs(
        self,
        workflow: str | None = None,
        limit: int = 50,
    ) -> list[ToolCallLog]:
        """Query tool_call_logs with optional workflow filter, newest first."""
        query = self.db.query(ToolCallLogORM)
        if workflow:
            query = query.filter(ToolCallLogORM.workflow == workflow)

        rows = query.order_by(ToolCallLogORM.id.desc()).limit(limit).all()
        return [
            ToolCallLog(
                logId=r.log_id,
                recordId=r.record_id,
                executedAt=str(r.executed_at),
                llmModel=r.llm_model,
                toolCallsJson=r.tool_calls_json,
                totalTools=r.total_tools,
                successfulTools=r.successful_tools,
                workflow=r.workflow,
                severity=r.severity,
            )
            for r in rows
        ]

    def get_all(
        self,
        workflow: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[EvaluationRecord]:
        """Query PostgreSQL for records, newest first, with optional filters."""
        query = self.db.query(IncidentRecordORM)

        if workflow:
            query = query.filter(IncidentRecordORM.workflow == workflow)
        if status:
            query = query.filter(IncidentRecordORM.eval_status == status)

        rows = query.order_by(IncidentRecordORM.id.desc()).limit(limit).all()
        return [self._to_record(row) for row in rows]

    def get_metrics(self) -> MetricsSummary:
        """
        Aggregate metrics from PostgreSQL.

        NOTE: this uses plain SQLAlchemy for now.
        In Step 4 we will load results into Pandas / Polars for richer
        time-series analytics, rolling averages, and histogram data.
        """
        rows = self.db.query(IncidentRecordORM).all()

        if not rows:
            return MetricsSummary(
                totalEvaluations=0,
                byStatus=[],
                averageScore=0.0,
                bySeverity={},
                topSuggestedActions=[],
                workflows=[],
            )

        status_counts = Counter(r.eval_status for r in rows)
        by_status = [
            StatusCount(status=s, count=c)  # type: ignore[arg-type]
            for s, c in status_counts.most_common()
        ]

        avg_score = sum(r.eval_score for r in rows) / len(rows)
        severity_counts: dict[str, int] = Counter(r.severity for r in rows)

        action_counts = Counter(
            r.suggested_action for r in rows if r.suggested_action is not None
        )
        top_actions = [
            ActionCount(action=a, count=c)
            for a, c in action_counts.most_common(5)
        ]

        return MetricsSummary(
            totalEvaluations=len(rows),
            byStatus=by_status,
            averageScore=round(avg_score, 2),
            bySeverity=dict(severity_counts),
            topSuggestedActions=top_actions,
            workflows=sorted({r.workflow for r in rows}),
        )

    # ── private helpers ───────────────────────────────────────────────────────

    def get_raw_rows(self) -> list[dict]:
        """
        Return a flat list-of-dicts for analytics consumption.

        Deliberately decoupled from Pydantic/ORM so both Pandas and Polars
        can construct their DataFrames without extra conversion layers.
        Only the columns needed by analytics.py are included.
        """
        rows = self.db.query(IncidentRecordORM).all()
        return [
            {
                "record_id": r.record_id,
                "received_at": r.received_at,       # datetime object
                "workflow": r.workflow,
                "severity": r.severity,
                "eval_status": r.eval_status,
                "eval_score": r.eval_score,
                "suggested_action": r.suggested_action,
            }
            for r in rows
        ]

    def _to_record(self, row: IncidentRecordORM) -> EvaluationRecord:
        """Reconstruct a Pydantic EvaluationRecord from an ORM row."""
        return EvaluationRecord(
            recordId=row.record_id,
            receivedAt=str(row.received_at),
            incident=StandardIncident.model_validate(row.incident_json),
            result=EvaluationResult.model_validate(row.result_json),
        )


# ── FastAPI dependency ─────────────────────────────────────────────────────────

def get_store(db: Session = Depends(get_db)) -> IncidentStore:
    """
    Inject an IncidentStore backed by a real PostgreSQL session.

    FastAPI resolves the chain automatically:
        get_store → Depends(get_db) → SQLAlchemy Session → IncidentStore

    All endpoints that declare `store: IncidentStore = Depends(get_store)`
    are unchanged from Step 2 — this is the payoff of Dependency Injection.
    """
    return IncidentStore(db)
