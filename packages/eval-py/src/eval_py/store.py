"""
In-memory store for evaluation records.

This is a temporary implementation for Step 2.
In Step 3 it will be replaced by a PostgreSQL-backed store using SQLAlchemy,
but all callers (endpoints, background tasks) will remain unchanged — that is
the point of using Dependency Injection with Depends().

The store is a module-level singleton: one shared instance per process.
"""
from __future__ import annotations

from collections import Counter

from .models import (
    ActionCount,
    EvaluationRecord,
    MetricsSummary,
    StatusCount,
)


class IncidentStore:
    def __init__(self) -> None:
        self._records: list[EvaluationRecord] = []

    # ── writes ────────────────────────────────────────────────────────────────

    def save(self, record: EvaluationRecord) -> None:
        self._records.append(record)

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_all(
        self,
        workflow: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[EvaluationRecord]:
        """Return records newest-first, optionally filtered by workflow or status."""
        records = self._records

        if workflow:
            records = [r for r in records if r.incident.workflow == workflow]
        if status:
            records = [r for r in records if r.result.status == status]

        # Newest first, capped at limit
        return list(reversed(records))[:limit]

    def get_metrics(self) -> MetricsSummary:
        """
        Compute aggregated metrics from all stored records.

        NOTE: this is plain Python for now.
        In Step 4 we will replace this with Pandas / Polars for richer analytics
        (time-series, rolling averages, histograms, etc.).
        """
        records = self._records

        if not records:
            return MetricsSummary(
                totalEvaluations=0,
                byStatus=[],
                averageScore=0.0,
                bySeverity={},
                topSuggestedActions=[],
                workflows=[],
            )

        # Count by EvaluationStatus
        status_counts = Counter(r.result.status for r in records)
        by_status = [
            StatusCount(status=s, count=c)          # type: ignore[arg-type]
            for s, c in status_counts.most_common()
        ]

        # Average score
        avg_score = sum(r.result.score for r in records) / len(records)

        # Count by incident severity
        severity_counts: dict[str, int] = Counter(r.incident.severity for r in records)

        # Top suggested actions (filter out None)
        action_counts = Counter(
            r.result.suggestedAction
            for r in records
            if r.result.suggestedAction is not None
        )
        top_actions = [
            ActionCount(action=a, count=c)
            for a, c in action_counts.most_common(5)
        ]

        # Distinct workflows seen
        workflows = sorted({r.incident.workflow for r in records})

        return MetricsSummary(
            totalEvaluations=len(records),
            byStatus=by_status,
            averageScore=round(avg_score, 2),
            bySeverity=dict(severity_counts),
            topSuggestedActions=top_actions,
            workflows=workflows,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
# One shared instance for the lifetime of the process.
# FastAPI's Depends() will always resolve to this same object.

_store = IncidentStore()


def get_store() -> IncidentStore:
    """
    FastAPI dependency — inject the shared store into any endpoint.

    Usage:
        @app.get("/incidents")
        def list_incidents(store: IncidentStore = Depends(get_store)):
            return store.get_all()
    """
    return _store
