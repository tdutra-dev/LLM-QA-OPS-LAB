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

try:
    from pgvector.sqlalchemy import Vector as PgVector
    _pgvector_available = True
except ImportError:
    PgVector = None  # type: ignore[assignment,misc]
    _pgvector_available = False

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

    # ── Step 12: RAG — pgvector embedding ────────────────────────────────────
    # 1536-dimensional vector from OpenAI text-embedding-3-small.
    # Nullable: records created before Step 12 will have NULL here.
    # pgvector must be installed as a PostgreSQL extension:
    #   CREATE EXTENSION IF NOT EXISTS vector;
    embedding: Mapped[list[float] | None] = mapped_column(
        PgVector(1536) if _pgvector_available else Text,  # type: ignore[arg-type]
        nullable=True,
    )

    def __repr__(self) -> str:  # type: ignore[override]
        return (
            f"<IncidentRecordORM id={self.id} record_id={self.record_id!r} "
            f"workflow={self.workflow!r} status={self.eval_status!r} score={self.eval_score}>"
        )


# ── Step 7: ActionExecutor audit log ─────────────────────────────────────────


class ActionLogORM(Base):
    """
    Persistent audit trail of every autonomous action taken by the ActionExecutor.

    One row = one executed (or skipped) action, linked to its triggering
    evaluation record via record_id.
    """
    __tablename__ = "action_logs"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Action identification ─────────────────────────────────────────────────
    action_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    # ── Timestamp (server-side for consistency) ───────────────────────────────
    executed_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Action metadata (denormalized for fast filtering) ─────────────────────
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)      # success|failed|skipped
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    workflow: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:  # type: ignore[override]
        return (
            f"<ActionLogORM id={self.id} action_id={self.action_id!r} "
            f"type={self.action_type!r} outcome={self.outcome!r} workflow={self.workflow!r}>"
        )


# ── Step 9: Tool Calling audit log ────────────────────────────────────────────


class ToolCallLogORM(Base):
    """
    Audit trail of LLM tool calling evaluations.

    Stores the LLM's tool choices and execution results for analysis.
    Complements ActionLogORM (individual actions) with multi-tool records.
    """
    __tablename__ = "tool_call_logs"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Log identification ────────────────────────────────────────────────────
    log_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    # ── Timestamp ──────────────────────────────────────────────────────────────
    executed_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Tool calling metadata ─────────────────────────────────────────────────
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_calls_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    total_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:  # type: ignore[override]
        return (
            f"<ToolCallLogORM id={self.id} log_id={self.log_id!r} "
            f"model={self.llm_model!r} tools={self.total_tools} workflow={self.workflow!r}>"
        )
