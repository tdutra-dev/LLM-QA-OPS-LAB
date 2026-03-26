"""
SQLAlchemy ORM model for evaluation records.

Maps the EvaluationRecord Pydantic model to a PostgreSQL table.

Design choice — JSONB columns for incident + result:
    Instead of creating separate tables for every nested field, we store the
    incident and result as JSONB. This keeps the schema simple for Step 3 and
    still allows PostgreSQL to index and query inside the JSON.
    In a production system you might normalize these into separate tables.

Table name: evaluation_records
"""
from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base


class IncidentRecordORM(Base):
    __tablename__ = "evaluation_records"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Record metadata ───────────────────────────────────────────────────────
    record_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    # `server_default=func.now()` lets PostgreSQL set the timestamp —
    # more reliable than Python time when the server is under load.
    received_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Incident fields (denormalized for fast filtering) ─────────────────────
    # These are duplicated from the JSONB column for efficient WHERE clauses.
    workflow: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # ── Evaluation result fields (denormalized) ───────────────────────────────
    eval_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    eval_score: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_action: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── Full payloads as JSONB ─────────────────────────────────────────────────
    # Preserves the complete incident + result for reconstruction and future analytics.
    incident_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ── Optional: free-text summary for quick display ─────────────────────────
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IncidentRecordORM id={self.id} record_id={self.record_id!r} "
            f"workflow={self.workflow!r} status={self.eval_status!r} score={self.eval_score}>"
        )
