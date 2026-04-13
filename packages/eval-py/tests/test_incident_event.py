"""
test_incident_event.py — Test suite per IncidentEvent (Fase 1).

Cosa testiamo:
- Costruzione valida per ogni source_system
- Auto-generazione di incident_id
- Normalizzazione del timestamp (stringa ISO, Z suffix, datetime naïve)
- Validators: service e message non possono essere blank
- derive_incident_type(): mapping error_type → incidentType
- to_standard_incident(): conversione verso il formato di evaluation
- Campi opzionali: error_type e affected_resource
- raw viene preservato invariato

Questi test non richiedono PostgreSQL, Redis, né OpenAI API.
Sono la test suite fast che deve restare sempre verde.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from eval_py.incident_event import IncidentEvent


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_event(**overrides) -> IncidentEvent:
    """Factory con valori di default sensati. Override selettivo nei test."""
    defaults = {
        "source_system": "spring-boot",
        "severity": "high",
        "service": "checkout-api",
        "message": "NullPointerException in PaymentService.process()",
        "timestamp": "2026-04-13T09:00:00Z",
        "raw": {"level": "ERROR", "thread": "http-nio-8080-exec-1"},
    }
    defaults.update(overrides)
    return IncidentEvent(**defaults)


# ── Costruzione valida ────────────────────────────────────────────────────────

class TestConstruction:

    @pytest.mark.parametrize("source_system", ["spring-boot", "kafka", "mysql", "generic"])
    def test_all_source_systems_are_valid(self, source_system: str):
        event = make_event(source_system=source_system)
        assert event.source_system == source_system

    def test_incident_id_is_auto_generated(self):
        event = make_event()
        assert event.incident_id
        assert len(event.incident_id) == 36  # UUID4 con trattini

    def test_two_events_have_different_ids(self):
        a = make_event()
        b = make_event()
        assert a.incident_id != b.incident_id

    def test_explicit_incident_id_is_preserved(self):
        event = make_event(incident_id="my-custom-id-001")
        assert event.incident_id == "my-custom-id-001"

    def test_raw_dict_is_preserved_unchanged(self):
        payload = {"level": "WARN", "code": 503, "tags": ["db", "timeout"]}
        event = make_event(raw=payload)
        assert event.raw == payload

    def test_optional_fields_default_to_none(self):
        event = make_event()
        assert event.error_type is None
        assert event.affected_resource is None

    def test_optional_fields_accepted_when_provided(self):
        event = make_event(
            error_type="schema_validation_failed",
            affected_resource="orders-table",
        )
        assert event.error_type == "schema_validation_failed"
        assert event.affected_resource == "orders-table"


# ── Validator: timestamp ──────────────────────────────────────────────────────

class TestTimestampValidator:

    def test_iso_string_with_z_suffix_is_parsed(self):
        event = make_event(timestamp="2026-04-13T09:00:00Z")
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_iso_string_with_offset_is_parsed(self):
        event = make_event(timestamp="2026-04-13T09:00:00+00:00")
        assert isinstance(event.timestamp, datetime)

    def test_naive_datetime_gets_utc_timezone(self):
        naive = datetime(2026, 4, 13, 9, 0, 0)
        event = make_event(timestamp=naive)
        assert event.timestamp.tzinfo == timezone.utc

    def test_aware_datetime_is_preserved(self):
        aware = datetime(2026, 4, 13, 9, 0, 0, tzinfo=timezone.utc)
        event = make_event(timestamp=aware)
        assert event.timestamp == aware

    def test_invalid_timestamp_raises_validation_error(self):
        with pytest.raises(ValidationError):
            make_event(timestamp="not-a-date")


# ── Validator: service e message ──────────────────────────────────────────────

class TestStringValidators:

    def test_blank_service_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            make_event(service="   ")
        assert "service" in str(exc_info.value)

    def test_empty_service_raises_validation_error(self):
        with pytest.raises(ValidationError):
            make_event(service="")

    def test_service_is_stripped(self):
        event = make_event(service="  checkout-api  ")
        assert event.service == "checkout-api"

    def test_blank_message_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            make_event(message="   ")
        assert "message" in str(exc_info.value)

    def test_empty_message_raises_validation_error(self):
        with pytest.raises(ValidationError):
            make_event(message="")

    def test_message_is_stripped(self):
        event = make_event(message="  Something went wrong  ")
        assert event.message == "Something went wrong"

    def test_invalid_source_system_raises_validation_error(self):
        with pytest.raises(ValidationError):
            make_event(source_system="oracle")  # type: ignore

    def test_invalid_severity_raises_validation_error(self):
        with pytest.raises(ValidationError):
            make_event(severity="catastrophic")  # type: ignore


# ── derive_incident_type ──────────────────────────────────────────────────────

class TestDeriveIncidentType:

    def test_none_error_type_returns_technical_error(self):
        event = make_event(error_type=None)
        assert event.derive_incident_type() == "technical_error"

    @pytest.mark.parametrize("error_type,expected", [
        ("schema_validation_failed", "schema_error"),
        ("json_parse_error", "schema_error"),
        ("validation_exception", "schema_error"),
        ("semantic_drift_detected", "semantic_error"),
        ("hallucination_detected", "semantic_error"),
        ("factual_inconsistency", "semantic_error"),
        ("quality_degradation", "semantic_error"),
        ("latency_spike", "degradation"),
        ("timeout_exceeded", "degradation"),
        ("slow_query_detected", "degradation"),
        ("degradation_alert", "degradation"),
        ("connection_refused", "technical_error"),
        ("out_of_memory", "technical_error"),
        ("unknown_error_xyz", "technical_error"),
    ])
    def test_error_type_mapping(self, error_type: str, expected: str):
        event = make_event(error_type=error_type)
        assert event.derive_incident_type() == expected

    def test_matching_is_case_insensitive(self):
        event = make_event(error_type="SCHEMA_VALIDATION_FAILED")
        assert event.derive_incident_type() == "schema_error"


# ── to_standard_incident ──────────────────────────────────────────────────────

class TestToStandardIncident:

    def test_returns_standard_incident_instance(self):
        from eval_py.models import StandardIncident
        event = make_event()
        si = event.to_standard_incident()
        assert isinstance(si, StandardIncident)

    def test_id_matches_incident_id(self):
        event = make_event(incident_id="fixed-id-001")
        si = event.to_standard_incident()
        assert si.id == "fixed-id-001"

    def test_workflow_is_service_name(self):
        event = make_event(service="payment-service")
        si = event.to_standard_incident()
        assert si.workflow == "payment-service"

    def test_severity_is_preserved(self):
        for severity in ["low", "medium", "high", "critical"]:
            event = make_event(severity=severity)  # type: ignore
            si = event.to_standard_incident()
            assert si.severity == severity

    def test_message_is_preserved(self):
        event = make_event(message="DB connection pool exhausted")
        si = event.to_standard_incident()
        assert si.message == "DB connection pool exhausted"

    @pytest.mark.parametrize("source_system,expected_stage", [
        ("spring-boot", "service"),
        ("kafka", "stream"),
        ("mysql", "database"),
        ("generic", "external"),
    ])
    def test_stage_mapping_by_source_system(self, source_system: str, expected_stage: str):
        event = make_event(source_system=source_system)
        si = event.to_standard_incident()
        assert si.stage == expected_stage

    def test_source_is_source_system(self):
        event = make_event(source_system="kafka")
        si = event.to_standard_incident()
        assert si.source == "kafka"

    def test_context_is_none_when_no_optional_fields(self):
        event = make_event(error_type=None, affected_resource=None)
        si = event.to_standard_incident()
        assert si.context is None

    def test_context_contains_error_type_when_present(self):
        event = make_event(error_type="schema_validation_failed")
        si = event.to_standard_incident()
        assert si.context is not None
        assert si.context["error_type"] == "schema_validation_failed"

    def test_context_contains_affected_resource_when_present(self):
        event = make_event(affected_resource="orders-table")
        si = event.to_standard_incident()
        assert si.context is not None
        assert si.context["affected_resource"] == "orders-table"

    def test_context_has_only_non_none_values(self):
        # Solo error_type presente, affected_resource assente
        event = make_event(error_type="schema_error", affected_resource=None)
        si = event.to_standard_incident()
        assert si.context is not None
        assert "affected_resource" not in si.context

    def test_incident_type_is_derived_correctly(self):
        event = make_event(error_type="schema_validation_failed")
        si = event.to_standard_incident()
        assert si.incidentType == "schema_error"

    def test_timestamp_is_iso_string(self):
        event = make_event(timestamp="2026-04-13T09:00:00Z")
        si = event.to_standard_incident()
        # deve essere una stringa ISO parsabile
        parsed = datetime.fromisoformat(si.timestamp)
        assert parsed.year == 2026

    def test_full_conversion_spring_boot_schema_error(self):
        """Test di integrazione end-to-end: SpringBoot schema error → StandardIncident."""
        event = IncidentEvent(
            incident_id="sb-001",
            source_system="spring-boot",
            severity="critical",
            service="checkout-api",
            message="JSON schema validation failed on /api/v1/orders",
            timestamp="2026-04-13T09:15:00Z",
            raw={
                "logger": "com.example.checkout.OrderController",
                "level": "ERROR",
                "exception": "SchemaValidationException",
            },
            error_type="json_schema_validation_failed",
            affected_resource="/api/v1/orders",
        )
        si = event.to_standard_incident()

        assert si.id == "sb-001"
        assert si.workflow == "checkout-api"
        assert si.stage == "service"
        assert si.incidentType == "schema_error"
        assert si.severity == "critical"
        assert si.source == "spring-boot"
        assert si.context["error_type"] == "json_schema_validation_failed"
        assert si.context["affected_resource"] == "/api/v1/orders"
