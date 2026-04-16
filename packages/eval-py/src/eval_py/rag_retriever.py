"""
Step 12 — RAG Retriever: pgvector-backed incident context retrieval.

Architecture
────────────
This module implements the Retrieval-Augmented Generation (RAG) layer for the
evaluation engine. Before calling the LLM to evaluate a new incident, we:

    1. EMBED       Generate a vector embedding for the new incident text
                   using OpenAI text-embedding-3-small (1536 dimensions).

    2. RETRIEVE    Query PostgreSQL (pgvector) for the top-K most similar
                   past incidents via cosine distance (<=> operator).

    3. AUGMENT     Format the retrieved incidents as structured context
                   that is injected into the LLM evaluation prompt.

This gives the LLM grounding in real historical precedents, reducing
hallucinations and improving remediation quality.

Design decisions
────────────────
- **OpenAI text-embedding-3-small**: 1536 dims, fast, cheap, same API key
  already used for tool-calling evaluation.

- **pgvector cosine distance**: <=> operator, returns 0 (identical) to 2 (opposite).
  We convert to similarity score = 1 - distance/2 for readability.

- **Graceful degradation**: if embeddings are unavailable (no API key, DB not
  ready), the retriever returns an empty list and the engine falls back to
  the standard rule-based evaluation — never raises to the caller.

- **No LlamaIndex yet**: raw pgvector access keeps zero new framework
  dependencies for Step 12. LlamaIndex refactor is planned for Step 13 as a
  clean pipeline abstraction layer on top.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Embedding model: 1536 dimensions, ~$0.02 / 1M tokens
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

# Number of similar incidents to retrieve by default
DEFAULT_TOP_K = 3


@dataclass
class SimilarIncident:
    """A past incident retrieved from the vector store with its similarity score."""
    record_id: str
    workflow: str
    incident_type: str
    severity: str
    summary: str
    suggested_action: str | None
    eval_status: str
    eval_score: int
    similarity: float   # 0.0–1.0, higher = more similar


def _incident_to_text(incident_json: dict) -> str:
    """
    Serialize an incident dict into a plain-text representation suitable for
    embedding. We focus on the semantically meaningful fields.
    """
    parts = [
        f"workflow: {incident_json.get('workflow', '')}",
        f"stage: {incident_json.get('stage', '')}",
        f"incident_type: {incident_json.get('incidentType', '')}",
        f"severity: {incident_json.get('severity', '')}",
        f"category: {incident_json.get('category', '')}",
        f"source: {incident_json.get('source', '')}",
        f"message: {incident_json.get('message', '')}",
    ]
    if ctx := incident_json.get("context"):
        parts.append(f"context: {json.dumps(ctx)}")
    return " | ".join(parts)


def generate_embedding(text: str) -> list[float] | None:
    """
    Generate a 1536-dim embedding vector for the given text using OpenAI.

    Returns None (with a warning) if the API call fails, allowing the caller
    to degrade gracefully instead of crashing.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[rag] OPENAI_API_KEY not set — skipping embedding generation")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as exc:
        logger.warning("[rag] embedding generation failed: %s", exc)
        return None


def store_embedding(
    db: "Session",
    record_id: str,
    incident_json: dict,
) -> bool:
    """
    Generate and persist the embedding for a stored evaluation record.

    Called from store.py after saving an EvaluationRecord.
    Returns True if the embedding was stored, False if skipped/failed.
    """
    try:
        from .db_models import IncidentRecordORM
        from pgvector.sqlalchemy import Vector  # noqa: F401 — needed to register type

        text = _incident_to_text(incident_json)
        embedding = generate_embedding(text)
        if embedding is None:
            return False

        orm = db.query(IncidentRecordORM).filter(
            IncidentRecordORM.record_id == record_id
        ).first()
        if orm is None:
            logger.warning("[rag] record %s not found for embedding update", record_id)
            return False

        orm.embedding = embedding  # type: ignore[assignment]
        db.commit()
        logger.info("[rag] embedding stored for record %s", record_id)
        return True
    except Exception as exc:
        logger.warning("[rag] store_embedding failed: %s", exc)
        return False


def find_similar_incidents(
    incident_json: dict,
    db: "Session",
    top_k: int = DEFAULT_TOP_K,
) -> list[SimilarIncident]:
    """
    Retrieve the top-K most semantically similar past incidents from PostgreSQL
    using pgvector cosine distance.

    Returns an empty list (never raises) if:
    - pgvector extension is not installed
    - No embeddings are stored yet
    - OpenAI API call fails
    - Any other unexpected error

    The cosine distance operator <=> returns values in [0, 2].
    We convert: similarity = 1 - (distance / 2) → range [0, 1].
    """
    try:
        from pgvector.sqlalchemy import Vector  # noqa: F401 — registers the type
        from sqlalchemy import text as sql_text

        query_text = _incident_to_text(incident_json)
        query_embedding = generate_embedding(query_text)
        if query_embedding is None:
            return []

        # Use raw SQL for the pgvector <=> operator (cosine distance)
        # ORDER BY cosine distance ASC → most similar first
        # FILTER embedding IS NOT NULL → skip records without embeddings
        sql = sql_text("""
            SELECT
                record_id,
                workflow,
                incident_type,
                severity,
                summary,
                suggested_action,
                eval_status,
                eval_score,
                (embedding <=> CAST(:query_vec AS vector)) AS distance
            FROM evaluation_records
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
        """)

        rows = db.execute(
            sql,
            {
                "query_vec": str(query_embedding),
                "top_k": top_k,
            },
        ).fetchall()

        results = []
        for row in rows:
            distance = float(row.distance)
            similarity = max(0.0, 1.0 - distance / 2.0)
            results.append(SimilarIncident(
                record_id=row.record_id,
                workflow=row.workflow,
                incident_type=row.incident_type,
                severity=row.severity,
                summary=row.summary or "",
                suggested_action=row.suggested_action,
                eval_status=row.eval_status,
                eval_score=row.eval_score,
                similarity=round(similarity, 3),
            ))

        logger.info("[rag] retrieved %d similar incidents (top_k=%d)", len(results), top_k)
        return results

    except Exception as exc:
        logger.warning("[rag] find_similar_incidents failed: %s", exc)
        return []


def build_rag_context(similar: list[SimilarIncident]) -> str:
    """
    Format similar incidents as a structured context block for LLM injection.

    Returns an empty string if no similar incidents are available, so the
    caller can skip the RAG section of the prompt cleanly.
    """
    if not similar:
        return ""

    lines = [
        "## Historical Context — Similar Past Incidents",
        "",
        "The following incidents from the operational history are semantically similar",
        "to the current one and may provide useful signal for evaluation:",
        "",
    ]
    for i, inc in enumerate(similar, 1):
        lines.append(
            f"### Incident {i} (similarity: {inc.similarity:.0%})"
        )
        lines.append(f"- **Workflow:** {inc.workflow}")
        lines.append(f"- **Type / Severity:** {inc.incident_type} / {inc.severity}")
        lines.append(f"- **Evaluation:** {inc.eval_status} (score {inc.eval_score})")
        if inc.summary:
            lines.append(f"- **Summary:** {inc.summary}")
        if inc.suggested_action:
            lines.append(f"- **Action taken:** {inc.suggested_action}")
        lines.append("")

    return "\n".join(lines)
