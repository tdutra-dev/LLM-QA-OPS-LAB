"""
test_normalizers.py — Test suite per i normalizer di ingestion (Fase 2).

Cosa testiamo:
- SpringBootNormalizer: campi standard, derivazione service dal logger,
  mapping log level → severity, estrazione error_type dall'exception
- KafkaNormalizer: service da headers/consumer_group/topic, timestamp epoch ms,
  derivazione error_type dall'error text
- WebhookNormalizer: riconoscimento alias di campo (PagerDuty, Alertmanager, minimo)
- Tutti i normalizer: output è sempre un IncidentEvent valido
- Integrazione: normalize() → to_standard_incident() → evaluate() funziona end-to-end
- /ingest/* endpoints via TestClient (senza DB+Redis)

Nessuna dipendenza esterna (no PostgreSQL, no Redis, no OpenAI).
"""
from __future__ import annotations

import pytest

from eval_py.incident_event import IncidentEvent
from eval_py.normalizers import (
    KafkaNormalizer,
    SpringBootNormalizer,
    WebhookNormalizer,
    NORMALIZER_REGISTRY,
)


# ── SpringBootNormalizer ──────────────────────────────────────────────────────

class TestSpringBootNormalizer:

    def setup_method(self):
        self.n = SpringBootNormalizer()

    def test_full_payload_produces_valid_incident_event(self):
        raw = {
            "timestamp": "2026-04-13T09:00:00Z",
            "level": "ERROR",
            "logger": "com.example.checkout.PaymentService",
            "thread": "http-nio-8080-exec-1",
            "message": "NullPointerException in process()",
            "service": "checkout-api",
            "exception": "java.lang.NullPointerException",
            "requestUri": "/api/v1/orders",
        }
        event = self.n.normalize(raw)
        assert isinstance(event, IncidentEvent)
        assert event.source_system == "spring-boot"

    def test_service_taken_from_explicit_field_when_present(self):
        raw = {
            "message": "error",
            "service": "payment-service",
            "logger": "com.example.other.SomeClass",
        }
        event = self.n.normalize(raw)
        assert event.service == "payment-service"

    def test_service_derived_from_logger_when_service_absent(self):
        raw = {
            "message": "error",
            "logger": "com.example.checkout.PaymentService",
        }
        event = self.n.normalize(raw)
        assert event.service == "checkout"

    def test_service_derived_from_short_logger(self):
        raw = {"message": "error", "logger": "com.example"}
        event = self.n.normalize(raw)
        assert event.service == "example"

    def test_service_falls_back_to_unknown_when_no_logger(self):
        event = self.n.normalize({"message": "error"})
        assert event.service == "unknown-service"

    @pytest.mark.parametrize("level,expected_severity", [
        ("FATAL", "critical"),
        ("ERROR", "high"),
        ("WARN", "medium"),
        ("WARNING", "medium"),
        ("INFO", "low"),
        ("DEBUG", "low"),
        ("TRACE", "low"),
    ])
    def test_log_level_maps_to_correct_severity(self, level, expected_severity):
        event = self.n.normalize({"message": "x", "level": level})
        assert event.severity == expected_severity

    def test_missing_level_defaults_to_medium(self):
        event = self.n.normalize({"message": "something happened"})
        assert event.severity == "medium"

    def test_error_type_extracted_from_exception_field(self):
        raw = {
            "message": "error",
            "exception": "java.lang.NullPointerException",
        }
        event = self.n.normalize(raw)
        assert event.error_type == "NullPointerException"

    def test_error_type_extracted_from_exception_class_field(self):
        raw = {
            "message": "error",
            "exceptionClass": "org.springframework.web.bind.MethodArgumentNotValidException",
        }
        event = self.n.normalize(raw)
        assert event.error_type == "MethodArgumentNotValidException"

    def test_error_type_is_none_when_no_exception(self):
        event = self.n.normalize({"message": "just a warning"})
        assert event.error_type is None

    def test_affected_resource_from_request_uri(self):
        raw = {"message": "error", "requestUri": "/api/v1/payments"}
        event = self.n.normalize(raw)
        assert event.affected_resource == "/api/v1/payments"

    def test_affected_resource_from_endpoint_field(self):
        raw = {"message": "error", "endpoint": "/api/v2/orders"}
        event = self.n.normalize(raw)
        assert event.affected_resource == "/api/v2/orders"

    def test_affected_resource_is_none_when_absent(self):
        event = self.n.normalize({"message": "error"})
        assert event.affected_resource is None

    def test_raw_payload_preserved_unchanged(self):
        raw = {"message": "error", "level": "ERROR", "custom_field": "custom_value"}
        event = self.n.normalize(raw)
        assert event.raw == raw

    def test_timestamp_parsed_from_iso_string(self):
        from datetime import datetime
        raw = {"message": "error", "timestamp": "2026-04-13T09:00:00Z"}
        event = self.n.normalize(raw)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.year == 2026

    def test_missing_timestamp_falls_back_to_now(self):
        from datetime import datetime
        event = self.n.normalize({"message": "error"})
        assert isinstance(event.timestamp, datetime)

    def test_accepts_at_timestamp_field(self):
        """Logstash/ECS format uses @timestamp."""
        from datetime import datetime
        raw = {"message": "error", "@timestamp": "2026-04-13T10:00:00Z"}
        event = self.n.normalize(raw)
        assert isinstance(event.timestamp, datetime)

    def test_msg_alias_for_message(self):
        raw = {"msg": "alternative message field"}
        event = self.n.normalize(raw)
        assert event.message == "alternative message field"


# ── KafkaNormalizer ───────────────────────────────────────────────────────────

class TestKafkaNormalizer:

    def setup_method(self):
        self.n = KafkaNormalizer()

    def test_full_payload_produces_valid_incident_event(self):
        raw = {
            "topic": "orders-events",
            "partition": 0,
            "offset": 12345,
            "timestamp": 1712998800000,  # epoch ms
            "consumer_group": "checkout-consumer",
            "error": "consumer lag exceeded threshold",
            "severity": "high",
        }
        event = self.n.normalize(raw)
        assert isinstance(event, IncidentEvent)
        assert event.source_system == "kafka"

    def test_service_from_headers_takes_priority(self):
        raw = {
            "message": "error",
            "headers": {"service": "order-service"},
            "consumer_group": "checkout-consumer",
        }
        event = self.n.normalize(raw)
        assert event.service == "order-service"

    def test_service_derived_from_consumer_group(self):
        raw = {"message": "error", "consumer_group": "checkout-consumer"}
        event = self.n.normalize(raw)
        assert event.service == "checkout"

    def test_consumer_group_suffix_group_removed(self):
        raw = {"message": "error", "consumer_group": "payment-group"}
        event = self.n.normalize(raw)
        assert event.service == "payment"

    def test_service_derived_from_topic_when_no_group(self):
        raw = {"message": "error", "topic": "orders-events"}
        event = self.n.normalize(raw)
        assert event.service == "orders"

    def test_service_unknown_when_no_hints(self):
        event = self.n.normalize({"message": "error"})
        assert event.service == "unknown-service"

    def test_epoch_ms_timestamp_parsed(self):
        from datetime import datetime, timezone
        raw = {"message": "error", "timestamp": 1712998800000}
        event = self.n.normalize(raw)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_affected_resource_is_topic(self):
        raw = {"message": "error", "topic": "orders-dlq"}
        event = self.n.normalize(raw)
        assert event.affected_resource == "orders-dlq"

    def test_explicit_error_type_wins_over_derived(self):
        raw = {
            "message": "error",
            "error": "consumer lag exceeded threshold",
            "error_type": "custom_type",
        }
        event = self.n.normalize(raw)
        assert event.error_type == "custom_type"

    @pytest.mark.parametrize("error_text,expected_type", [
        ("consumer lag exceeded threshold", "consumer_lag"),
        ("connection timed out", "timeout_exceeded"),
        ("schema registry deserialization error", "schema_validation_failed"),
        ("dead letter queue entry received", "dlq_entry"),
        ("unexpected error code 500", "technical_error"),
    ])
    def test_error_type_derived_from_error_text(self, error_text, expected_type):
        raw = {"message": "irrelevant", "error": error_text}
        event = self.n.normalize(raw)
        assert event.error_type == expected_type

    def test_error_type_none_when_no_error_field(self):
        event = self.n.normalize({"message": "normal event"})
        assert event.error_type is None

    def test_severity_from_explicit_field(self):
        event = self.n.normalize({"message": "x", "severity": "critical"})
        assert event.severity == "critical"

    def test_missing_severity_defaults_to_medium(self):
        event = self.n.normalize({"message": "x"})
        assert event.severity == "medium"

    def test_message_from_error_field(self):
        raw = {"error": "consumer lag exceeded threshold"}
        event = self.n.normalize(raw)
        assert event.message == "consumer lag exceeded threshold"

    def test_message_fallback_uses_topic(self):
        raw = {"topic": "orders-events"}
        event = self.n.normalize(raw)
        assert "orders-events" in event.message


# ── WebhookNormalizer ─────────────────────────────────────────────────────────

class TestWebhookNormalizer:

    def setup_method(self):
        self.n = WebhookNormalizer()

    def test_pagerduty_style_payload(self):
        raw = {
            "id": "PD-12345",
            "severity": "critical",
            "summary": "Database connection pool exhausted",
            "service": "database-service",
            "created_at": "2026-04-13T09:00:00Z",
        }
        event = self.n.normalize(raw)
        assert isinstance(event, IncidentEvent)
        assert event.source_system == "generic"
        assert event.severity == "critical"
        assert event.service == "database-service"
        assert event.message == "Database connection pool exhausted"

    def test_alertmanager_style_payload(self):
        raw = {
            "labels": {},
            "component": "prometheus",
            "description": "High error rate detected",
            "severity": "high",
            "fired_at": "2026-04-13T09:00:00Z",
        }
        event = self.n.normalize(raw)
        assert event.service == "prometheus"
        assert event.message == "High error rate detected"

    def test_github_actions_style_payload(self):
        raw = {
            "title": "Build failed on main",
            "app": "backend-api",
            "level": "error",
            "time": "2026-04-13T09:05:00Z",
        }
        event = self.n.normalize(raw)
        assert event.service == "backend-api"
        assert "Build failed" in event.message
        assert event.severity == "high"

    def test_minimal_payload_produces_valid_event(self):
        raw = {"message": "something bad happened"}
        event = self.n.normalize(raw)
        assert isinstance(event, IncidentEvent)
        assert event.message == "something bad happened"
        assert event.service == "unknown-service"
        assert event.severity == "medium"

    def test_completely_empty_payload_produces_valid_event(self):
        """Even an empty dict must not raise — fallbacks kick in."""
        event = self.n.normalize({})
        assert isinstance(event, IncidentEvent)
        assert event.message == "Webhook event received"
        assert event.service == "unknown-service"

    @pytest.mark.parametrize("alias,value", [
        ("severity", "critical"),
        ("level", "high"),
        ("priority", "medium"),
        ("urgency", "low"),
    ])
    def test_severity_aliases(self, alias, value):
        event = self.n.normalize({"message": "x", alias: value})
        assert event.severity == value  # type: ignore

    @pytest.mark.parametrize("alias", ["summary", "description", "text", "body", "title", "alert_name"])
    def test_message_aliases_all_recognized(self, alias):
        raw = {alias: "the incident message"}
        event = self.n.normalize(raw)
        assert event.message == "the incident message"

    @pytest.mark.parametrize("alias", ["service_name", "component", "source", "app", "application"])
    def test_service_aliases_all_recognized(self, alias):
        raw = {"message": "x", alias: "my-service"}
        event = self.n.normalize(raw)
        assert event.service == "my-service"

    def test_error_type_from_error_type_field(self):
        raw = {"message": "x", "error_type": "schema_validation_failed"}
        event = self.n.normalize(raw)
        assert event.error_type == "schema_validation_failed"

    def test_affected_resource_from_resource_field(self):
        raw = {"message": "x", "resource": "arn:aws:rds:eu-west-1:123:db/prod"}
        event = self.n.normalize(raw)
        assert event.affected_resource == "arn:aws:rds:eu-west-1:123:db/prod"

    def test_raw_preserved(self):
        raw = {"message": "x", "custom": 42}
        event = self.n.normalize(raw)
        assert event.raw == raw


# ── NORMALIZER_REGISTRY ───────────────────────────────────────────────────────

class TestNormalizerRegistry:

    def test_all_expected_keys_present(self):
        assert "spring-boot" in NORMALIZER_REGISTRY
        assert "kafka" in NORMALIZER_REGISTRY
        assert "generic" in NORMALIZER_REGISTRY

    def test_registry_instances_are_correct_types(self):
        assert isinstance(NORMALIZER_REGISTRY["spring-boot"], SpringBootNormalizer)
        assert isinstance(NORMALIZER_REGISTRY["kafka"], KafkaNormalizer)
        assert isinstance(NORMALIZER_REGISTRY["generic"], WebhookNormalizer)


# ── Integrazione: normalize → to_standard_incident → evaluate ─────────────────

class TestNormalizerToEvaluationIntegration:
    """
    Verifica che il flusso completo funzioni end-to-end senza servizi esterni.

    normalize(raw) → IncidentEvent → to_standard_incident() → evaluate()
    """

    def test_spring_boot_error_evaluates_to_critical_or_needs_attention(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest

        raw = {
            "level": "ERROR",
            "message": "NullPointerException in process()",
            "exception": "java.lang.NullPointerException",
            "service": "checkout-api",
        }
        event = SpringBootNormalizer().normalize(raw)
        standard = event.to_standard_incident()
        result = evaluate(EvaluationRequest(incident=standard))

        assert result.status in ("critical", "needs_attention")
        assert 0 <= result.score <= 100
        assert result.summary

    def test_kafka_schema_error_evaluates_to_critical(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest

        raw = {
            "topic": "orders-events",
            "error": "schema registry deserialization error",
            "severity": "critical",
            "consumer_group": "checkout-consumer",
        }
        event = KafkaNormalizer().normalize(raw)
        standard = event.to_standard_incident()
        result = evaluate(EvaluationRequest(incident=standard))

        assert result.status in ("critical", "needs_attention")
        assert result.suggestedAction is not None

    def test_webhook_low_severity_evaluates_to_ok_or_needs_attention(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest

        raw = {
            "severity": "low",
            "message": "Scheduled maintenance notification",
            "service": "infra-team",
        }
        event = WebhookNormalizer().normalize(raw)
        standard = event.to_standard_incident()
        result = evaluate(EvaluationRequest(incident=standard))

        assert result.status in ("ok", "needs_attention")


# ── /ingest/* HTTP endpoints ──────────────────────────────────────────────────

class TestIngestEndpoints:
    """
    Test gli endpoint /ingest/* via TestClient.
    Nessun DB reale — usa il store in-memory del test.
    """

    @pytest.fixture
    def client(self):
        """
        Crea un TestClient con dipendenze override per evitare DB/Redis.

        Problema: IncidentStore.save() chiama db.add() e db.commit() su una
        vera Session SQLAlchemy. In test, usiamo un MockStore che mantiene i
        record in memoria senza toccare il DB.

        Facciamo anche il mock delle operazioni DB nel lifespan FastAPI (pgvector
        check e create_all) che altrimenti tentano di connettersi a Postgres.
        """
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        from eval_py.main import app
        from eval_py.store import get_store
        from eval_py.models import EvaluationRecord, ActionLog, ToolCallLog

        class MockStore:
            """In-memory store per i test: nessuna dipendenza da DB/Redis."""
            def __init__(self):
                self._records: list[EvaluationRecord] = []
                self._actions: list[ActionLog] = []
                self._tool_call_logs: list[ToolCallLog] = []

            def save(self, record: EvaluationRecord) -> None:
                self._records.append(record)

            def save_action(self, action_log: ActionLog) -> None:
                self._actions.append(action_log)

            def save_tool_call_log(self, log: ToolCallLog) -> None:
                self._tool_call_logs.append(log)

            def get_all(self, **kwargs):
                return self._records

            def get_metrics(self):
                from eval_py.models import MetricsSummary
                return MetricsSummary(
                    totalEvaluations=len(self._records),
                    byStatus=[],
                    averageScore=0.0,
                    bySeverity={},
                    topSuggestedActions=[],
                    workflows=[],
                )

            def get_actions(self, **kwargs):
                return self._actions

        test_store = MockStore()
        app.dependency_overrides[get_store] = lambda: test_store

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_session = MagicMock()
        mock_session.close = MagicMock()

        with (
            patch("eval_py.main.engine.connect", return_value=mock_conn),
            patch("eval_py.main.Base.metadata.create_all"),
            patch("eval_py.main.SessionLocal", return_value=mock_session),
        ):
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c

        app.dependency_overrides.clear()

    def test_ingest_http_log_returns_200(self, client):
        payload = {
            "level": "ERROR",
            "message": "Connection refused",
            "service": "payment-api",
        }
        resp = client.post("/ingest/http-log", json=payload)
        assert resp.status_code == 200

    def test_ingest_http_log_response_has_expected_fields(self, client):
        payload = {
            "level": "ERROR",
            "message": "NullPointerException",
            "service": "checkout-api",
        }
        data = client.post("/ingest/http-log", json=payload).json()
        assert data["source_system"] == "spring-boot"
        assert data["service"] == "checkout-api"
        assert data["severity"] == "high"
        assert data["incident_id"]
        assert data["evaluation_status"] in ("ok", "needs_attention", "critical")
        assert 0 <= data["evaluation_score"] <= 100

    def test_ingest_kafka_event_returns_200(self, client):
        payload = {
            "topic": "orders-events",
            "consumer_group": "checkout-consumer",
            "error": "consumer lag exceeded threshold",
            "severity": "high",
        }
        resp = client.post("/ingest/kafka-event", json=payload)
        assert resp.status_code == 200

    def test_ingest_kafka_event_source_system_is_kafka(self, client):
        payload = {"topic": "payments", "error": "lag too high"}
        data = client.post("/ingest/kafka-event", json=payload).json()
        assert data["source_system"] == "kafka"

    def test_ingest_webhook_returns_200(self, client):
        payload = {
            "severity": "critical",
            "summary": "Database connection pool exhausted",
            "service": "db-service",
        }
        resp = client.post("/ingest/webhook", json=payload)
        assert resp.status_code == 200

    def test_ingest_webhook_source_system_is_generic(self, client):
        payload = {"message": "alert fired", "service": "infra"}
        data = client.post("/ingest/webhook", json=payload).json()
        assert data["source_system"] == "generic"

    def test_ingest_webhook_empty_payload_returns_200(self, client):
        """Webhook normalizer deve gestire payload vuoto senza errori."""
        resp = client.post("/ingest/webhook", json={})
        assert resp.status_code == 200
