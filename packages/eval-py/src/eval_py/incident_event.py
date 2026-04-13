"""
incident_event.py — Universal normalized incident model.

This is the canonical format for any incident entering the system,
regardless of source (Spring Boot, Kafka, MySQL, generic webhook).

All ingestion normalizers produce an IncidentEvent as output.
The batch analyzer and evaluation layer consume IncidentEvent objects.

Perché questo modello esiste:
- Ogni sistema esterno (Java, Kafka, MySQL...) emette eventi in formati diversi.
- L'ingestion layer normalizza tutto verso questo contratto unico.
- Una volta normalizzato, il batch analyzer può valutarlo con una sola logica.
- L'evaluation layer (correctness, hallucination, RAG faithfulness) si appoggia
  su questo contratto — non su formati arbitrari.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# ── Type aliases ──────────────────────────────────────────────────────────────

SourceSystem = Literal["spring-boot", "kafka", "mysql", "generic"]
SeverityLevel = Literal["low", "medium", "high", "critical"]

# Maps source_system → processing stage label used in StandardIncident
_STAGE_MAP: dict[str, str] = {
    "spring-boot": "service",
    "kafka": "stream",
    "mysql": "database",
    "generic": "external",
}


# ── Model ─────────────────────────────────────────────────────────────────────

class IncidentEvent(BaseModel):
    """
    Universal normalized incident event.

    Fields:
    - incident_id: auto-generated UUID, stable identifier for the event
    - source_system: the producing system (determines normalizer + stage label)
    - severity: how critical the event is
    - service: name of the service that produced the event (e.g. "checkout-api")
    - message: human-readable description of what happened
    - timestamp: when the event occurred (always UTC after validation)
    - raw: the original payload as received — preserved for audit and RAG context
    - error_type: optional freeform error code (drives incident type derivation)
    - affected_resource: optional URI/name of the resource involved
    """

    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    source_system: SourceSystem
    severity: SeverityLevel
    service: str
    message: str
    timestamp: datetime
    raw: dict[str, Any]
    error_type: str | None = None
    affected_resource: str | None = None

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("service")
    @classmethod
    def service_must_not_be_blank(cls, v: str) -> str:
        """Service name must identify a real service, not an empty string."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("service must not be blank")
        return stripped

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, v: str) -> str:
        """Message must carry meaningful information."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_and_normalize_timestamp(cls, v: Any) -> datetime:
        """
        Accept ISO 8601 strings (with or without Z suffix) or datetime objects.
        Naïve datetimes are assumed UTC and annotated accordingly.

        Perché: i sistemi esterni mandano timestamp in formati diversi.
        Normalizzare a UTC qui significa che tutto il sistema lavora
        su un'unica timeline coerente.
        """
        if isinstance(v, str):
            # Replace Z suffix for Python < 3.11 compatibility
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(f"Cannot parse timestamp from value: {v!r}")

    # ── Derived logic ─────────────────────────────────────────────────────────

    def derive_incident_type(self) -> str:
        """
        Map error_type string → StandardIncident incidentType.

        This is a heuristic — it covers the common cases. Unusual error_type
        strings fall back to "technical_error", which is always safe.

        Perché Literal e non Enum: mantiene compatibilità diretta con
        StandardIncident senza import circolare.
        """
        if not self.error_type:
            return "technical_error"

        et = self.error_type.lower()

        if "schema" in et or "validation" in et or "json" in et:
            return "schema_error"
        if "semantic" in et or "quality" in et or "hallucin" in et or "factual" in et:
            return "semantic_error"
        if "degradation" in et or "latency" in et or "slow" in et or "timeout" in et:
            return "degradation"

        return "technical_error"

    def to_standard_incident(self) -> "StandardIncident":
        """
        Convert this IncidentEvent into a StandardIncident for evaluation.

        StandardIncident is the format the evaluation engine, tool-calling layer,
        and RAG retriever all expect. This method is the bridge between the
        ingestion layer (universal) and the evaluation layer (opinionated).

        Usage:
            event = IncidentEvent(...)
            result = evaluate(EvaluationRequest(incident=event.to_standard_incident()))
        """
        from eval_py.models import StandardIncident

        context: dict[str, Any] | None = None
        if self.error_type or self.affected_resource:
            context = {
                k: v
                for k, v in {
                    "error_type": self.error_type,
                    "affected_resource": self.affected_resource,
                }.items()
                if v is not None
            }

        return StandardIncident(
            id=self.incident_id,
            timestamp=self.timestamp.isoformat(),
            workflow=self.service,
            stage=_STAGE_MAP[self.source_system],
            incidentType=self.derive_incident_type(),  # type: ignore[arg-type]
            category=self.source_system,
            severity=self.severity,
            source=self.source_system,
            message=self.message,
            context=context,
        )
