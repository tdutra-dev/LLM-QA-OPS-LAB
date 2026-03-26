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
from .db_models import IncidentRecordORM
from .models import (
    ActionCount,
    EvaluationRecord,
    EvaluationResult,
    MetricsSummary,
    StandardIncident,
    StatusCount,
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

    # ── reads ─────────────────────────────────────────────────────────────────

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
