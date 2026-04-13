"""
normalizers.py — Ingestion normalizers for each supported source system.

Il problema che risolviamo:
  Spring Boot emette log così: {"level": "ERROR", "logger": "com.example...", ...}
  Kafka emette eventi così:    {"topic": "orders", "consumer_group": "...", ...}
  Un webhook PagerDuty/GitHub: {"severity": "critical", "summary": "...", ...}

  → Tutti e tre devono diventare IncidentEvent, il formato universale del sistema.

Pattern: Strategy
  Ogni normalizer è una classe autonoma con un metodo `normalize(raw) → IncidentEvent`.
  L'endpoint /ingest/* sceglie il normalizer giusto in base al path, non alla logica
  del payload — questo li rende testabili in isolamento.

Aggiungere un nuovo sistema sorgente = aggiungere una nuova classe qui + un endpoint.
Nessun altro file cambia.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from .incident_event import IncidentEvent, SeverityLevel


# ── Protocol (interfaccia comune) ─────────────────────────────────────────────

class Normalizer(Protocol):
    """
    Interfaccia che ogni normalizer deve rispettare.

    Perché Protocol e non ABC:
    - Non serve ereditarietà — basta la duck typing strutturale.
    - I normalizer possono essere istanziati e testati senza alcuna base class.
    - Permette di aggiungere normalizer da plugin esterni senza import circolari.
    """

    def normalize(self, raw: dict[str, Any]) -> IncidentEvent:
        """Convert a raw source payload to a normalized IncidentEvent."""
        ...


# ── Helpers condivisi ─────────────────────────────────────────────────────────

_LOG_LEVEL_TO_SEVERITY: dict[str, SeverityLevel] = {
    "fatal": "critical",
    "error": "high",
    "warn": "medium",
    "warning": "medium",
    "info": "low",
    "debug": "low",
    "trace": "low",
}

_GENERIC_SEVERITY_MAP: dict[str, SeverityLevel] = {
    "critical": "critical",
    "high": "high",
    "error": "high",
    "medium": "medium",
    "warning": "medium",
    "warn": "medium",
    "low": "low",
    "info": "low",
}


def _map_log_level(level: str | None) -> SeverityLevel:
    """Map a log level string to a SeverityLevel. Defaults to 'medium'."""
    if not level:
        return "medium"
    return _LOG_LEVEL_TO_SEVERITY.get(level.lower(), "medium")


def _map_generic_severity(severity: str | None) -> SeverityLevel:
    """Map a generic severity string to a SeverityLevel. Defaults to 'medium'."""
    if not severity:
        return "medium"
    return _GENERIC_SEVERITY_MAP.get(severity.lower(), "medium")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime:
    """
    Try to parse a timestamp from a raw payload field.
    Falls back to now() if the value is missing or unparsable.

    Perché il fallback: normalizer non deve bloccare l'ingestion per un timestamp
    malformato — meglio un evento con timestamp approssimato che perdere il payload.
    """
    if not value:
        return _now_utc()
    try:
        if isinstance(value, (int, float)):
            # Unix milliseconds (Kafka standard)
            divisor = 1000 if value > 1e10 else 1
            return datetime.fromtimestamp(value / divisor, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
    except (ValueError, OSError):
        pass
    return _now_utc()


# ── SpringBootNormalizer ──────────────────────────────────────────────────────

class SpringBootNormalizer:
    """
    Normalizza un log JSON prodotto da un'applicazione Spring Boot (Logback/Log4j2).

    Formato atteso (tutti i campi sono opzionali tranne message):
    {
        "timestamp":  "2026-04-13T09:00:00Z",     # o epoch ms
        "level":      "ERROR",                      # log level
        "logger":     "com.example.checkout.PaymentService",
        "thread":     "http-nio-8080-exec-1",
        "message":    "NullPointerException in process()",
        "service":    "checkout-api",               # se non c'è, si estrae dal logger
        "exception":  "java.lang.NullPointerException",
        "requestUri": "/api/v1/orders",             # endpoint coinvolto (opzionale)
    }

    Campi extra vengono preservati in raw.

    Perché estraiamo service dal logger:
    In molti setup Spring Boot il campo "service" non è nel log strutturato.
    Il logger name (com.example.checkout.PaymentService) identifica implicitamente
    il modulo — prendiamo il secondo segmento del package come service name.
    """

    def normalize(self, raw: dict[str, Any]) -> IncidentEvent:
        service = self._extract_service(raw)
        message = raw.get("message") or raw.get("msg") or "No message"

        return IncidentEvent(
            source_system="spring-boot",
            severity=_map_log_level(raw.get("level")),
            service=service,
            message=str(message),
            timestamp=_parse_timestamp(raw.get("timestamp") or raw.get("@timestamp")),
            raw=raw,
            error_type=self._extract_error_type(raw),
            affected_resource=raw.get("requestUri") or raw.get("endpoint"),
        )

    def _extract_service(self, raw: dict[str, Any]) -> str:
        if raw.get("service"):
            return str(raw["service"])

        logger = raw.get("logger") or raw.get("loggerName") or ""
        parts = str(logger).split(".")
        # com.example.checkout.PaymentService → "checkout"
        # Fall back to the last meaningful segment if short
        if len(parts) >= 3:
            return parts[2]
        if len(parts) == 2:
            return parts[1]
        if parts and parts[0]:
            return parts[0]

        return "unknown-service"

    def _extract_error_type(self, raw: dict[str, Any]) -> str | None:
        # Prefer explicit exception field, then stack_trace prefix
        exception = raw.get("exception") or raw.get("exceptionClass")
        if exception:
            # "java.lang.NullPointerException" → "NullPointerException"
            return str(exception).split(".")[-1]
        return None


# ── KafkaNormalizer ───────────────────────────────────────────────────────────

class KafkaNormalizer:
    """
    Normalizza un evento Kafka (consumer error, lag alert, DLQ entry).

    Formato atteso:
    {
        "topic":          "orders-events",
        "partition":      0,
        "offset":         12345,
        "timestamp":      1712998800000,   # epoch ms (standard Kafka)
        "key":            "order-123",
        "consumer_group": "checkout-consumer",
        "error":          "consumer lag exceeded threshold",
        "error_type":     "consumer_lag",   # opzionale
        "severity":       "high",           # opzionale, default "high"
        "value":          {...},            # payload originale del messaggio
        "headers":        {"service": "order-service"},
    }

    Service detection priority:
    1. headers.service
    2. consumer_group (strip "-consumer" suffix)
    3. topic (primo segmento prima di "-")
    """

    def normalize(self, raw: dict[str, Any]) -> IncidentEvent:
        service = self._extract_service(raw)
        message = (
            raw.get("error")
            or raw.get("message")
            or f"Kafka event on topic {raw.get('topic', 'unknown')}"
        )

        return IncidentEvent(
            source_system="kafka",
            severity=_map_generic_severity(raw.get("severity")),
            service=service,
            message=str(message),
            timestamp=_parse_timestamp(raw.get("timestamp")),
            raw=raw,
            error_type=raw.get("error_type") or self._derive_error_type(raw),
            affected_resource=raw.get("topic"),
        )

    def _extract_service(self, raw: dict[str, Any]) -> str:
        headers = raw.get("headers") or {}
        if isinstance(headers, dict) and headers.get("service"):
            return str(headers["service"])

        consumer_group = raw.get("consumer_group") or raw.get("groupId")
        if consumer_group:
            # "checkout-consumer" → "checkout"
            return str(consumer_group).removesuffix("-consumer").removesuffix("-group")

        topic = raw.get("topic") or ""
        if topic:
            return str(topic).split("-")[0] or str(topic)

        return "unknown-service"

    def _derive_error_type(self, raw: dict[str, Any]) -> str | None:
        error = str(raw.get("error") or "").lower()
        if not error:
            return None
        if "lag" in error:
            return "consumer_lag"
        if "timeout" in error or "timed out" in error:
            return "timeout_exceeded"
        if "schema" in error or "deserialization" in error:
            return "schema_validation_failed"
        if "dlq" in error or "dead letter" in error:
            return "dlq_entry"
        return "technical_error"


# ── WebhookNormalizer ─────────────────────────────────────────────────────────

class WebhookNormalizer:
    """
    Normalizza un webhook generico (PagerDuty, GitHub Actions, Alertmanager, ecc.).

    Supporta varianti di campo comuni:
    - severity: "severity", "level", "priority"
    - message:  "message", "summary", "description", "text", "body", "title"
    - service:  "service", "service_name", "component", "source", "app"
    - timestamp:"timestamp", "fired_at", "created_at", "time"

    Perché è "generic": i webhook arrivano da sistemi diversi con naming conventions
    diverse. La strategia è cercare in un set di alias noti per ogni campo semantico.

    Il campo `source_system` è "generic" — il category in StandardIncident rifletterà
    questo, segnalando all'engine che l'evento viene da un sistema non nativo.
    """

    _SEVERITY_ALIASES = ("severity", "level", "priority", "urgency")
    _MESSAGE_ALIASES = ("message", "summary", "description", "text", "body", "title", "alert_name")
    _SERVICE_ALIASES = ("service", "service_name", "component", "source", "app", "application", "name")
    _TIMESTAMP_ALIASES = ("timestamp", "fired_at", "created_at", "time", "event_time", "occurred_at")

    def normalize(self, raw: dict[str, Any]) -> IncidentEvent:
        return IncidentEvent(
            source_system="generic",
            severity=_map_generic_severity(self._find(raw, self._SEVERITY_ALIASES)),
            service=self._find(raw, self._SERVICE_ALIASES) or "unknown-service",
            message=self._find(raw, self._MESSAGE_ALIASES) or "Webhook event received",
            timestamp=_parse_timestamp(self._find(raw, self._TIMESTAMP_ALIASES)),
            raw=raw,
            error_type=raw.get("error_type") or raw.get("alert_name") or raw.get("type"),
            affected_resource=raw.get("resource") or raw.get("endpoint") or raw.get("url"),
        )

    def _find(self, raw: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
        """Return the first non-empty value found among the given field aliases."""
        for key in aliases:
            val = raw.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return None


# ── Registry ──────────────────────────────────────────────────────────────────

# Mappa source_system → normalizer instance, usata dagli endpoint /ingest/*.
# Aggiungere un nuovo sistema = aggiungere una riga qui.
NORMALIZER_REGISTRY: dict[str, Normalizer] = {
    "spring-boot": SpringBootNormalizer(),
    "kafka": KafkaNormalizer(),
    "generic": WebhookNormalizer(),
}
