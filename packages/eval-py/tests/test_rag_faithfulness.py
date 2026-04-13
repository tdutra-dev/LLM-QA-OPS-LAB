"""
test_rag_faithfulness.py — Test suite per il RAG Faithfulness Evaluator (Fase 4).

Cosa testiamo:
- _extract_event_facts(): services, incident_types, severities estratti correttamente
- _check_services_grounding(): ratio corretta, claim ungrounded identificate
- _check_incident_types_grounding(): ratio corretta, types ungrounded identificati
- _check_critical_pattern_grounding(): references real entity, returns True per None
- _check_severity_consistency(): underreport, overreport, range ambiguo
- _compute_rule_score(): pesi corretti, score 0-100
- _verdict(): soglie faithful/partially_faithful/hallucinated
- evaluate_faithfulness(): integrazione completa, LLM judge mock, fallback

Nessuna dipendenza esterna — OpenAI viene sempre mockato o aggirato.
La fixture no_openai_key di conftest.py rimuove OPENAI_API_KEY per default.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from eval_py.models import (
    BatchAnalysisResult,
    BatchEventSummary,
    FaithfulnessResult,
    FaithfulnessRuleChecks,
)
from eval_py.rag_faithfulness import (
    _check_critical_pattern_grounding,
    _check_incident_types_grounding,
    _check_services_grounding,
    _check_severity_consistency,
    _compute_rule_score,
    _extract_event_facts,
    _verdict,
    evaluate_faithfulness,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def make_events(
    services: list[str] | None = None,
    incident_types: list[str] | None = None,
    severities: list[str] | None = None,
) -> list[dict]:
    """Builds a list of synthetic events for testing."""
    services = services or ["checkout-api"]
    incident_types = incident_types or ["technical_error"]
    severities = severities or ["high"]

    n = max(len(services), len(incident_types), len(severities))
    events = []
    for i in range(n):
        events.append(
            {
                "incident_id": f"inc-{i:03d}",
                "service": services[i % len(services)],
                "incident_type": incident_types[i % len(incident_types)],
                "severity": severities[i % len(severities)],
                "message": f"Error {i}",
                "source_system": "spring-boot",
            }
        )
    return events


def make_batch_result(
    batch_id: str = "batch_test01",
    services_affected: list[str] | None = None,
    overall_assessment: str = "System appears stable.",
    critical_pattern: str | None = None,
    events_by_service: list[BatchEventSummary] | None = None,
    hallucination_risk: str = "low",
    confidence_score: int = 75,
    llm_used: bool = True,
) -> BatchAnalysisResult:
    return BatchAnalysisResult(
        batch_id=batch_id,
        analyzed_at="2026-04-13T10:00:00+00:00",
        event_count=3,
        window_seconds=300,
        services_affected=services_affected or ["checkout-api"],
        overall_assessment=overall_assessment,
        critical_pattern=critical_pattern,
        recommended_actions=["Monitor"],
        events_by_service=events_by_service or [
            BatchEventSummary(
                service="checkout-api",
                count=3,
                dominant_severity="high",
                incident_types=["technical_error"],
            )
        ],
        hallucination_risk=hallucination_risk,  # type: ignore[arg-type]
        confidence_score=confidence_score,
        llm_used=llm_used,
    )


def _make_judge_response(score: int, claims: list[str], verdict: str) -> MagicMock:
    """Builds a mock OpenAI response for the LLM judge."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        {
            "faithfulness_score": score,
            "ungrounded_claims": claims,
            "verdict": verdict,
        }
    )
    return mock_resp


# ── _extract_event_facts ──────────────────────────────────────────────────────

class TestExtractEventFacts:

    def test_returns_real_services(self):
        events = make_events(services=["svc-a", "svc-b"])
        services, _, _ = _extract_event_facts(events)
        assert "svc-a" in services
        assert "svc-b" in services

    def test_returns_real_incident_types(self):
        events = make_events(incident_types=["schema_error", "degradation"])
        _, types, _ = _extract_event_facts(events)
        assert "schema_error" in types
        assert "degradation" in types

    def test_returns_severities_list(self):
        events = make_events(severities=["critical", "high", "low"])
        _, _, severities = _extract_event_facts(events)
        assert "critical" in severities
        assert "high" in severities
        assert "low" in severities

    def test_empty_events(self):
        services, types, severities = _extract_event_facts([])
        assert services == set()
        assert types == set()
        assert severities == []

    def test_fallback_service_unknown(self):
        events = [{"message": "error"}]  # no 'service' key
        services, _, _ = _extract_event_facts(events)
        assert "unknown" in services

    def test_uses_incidentType_field(self):
        events = [{"service": "s", "incidentType": "semantic_error", "severity": "low"}]
        _, types, _ = _extract_event_facts(events)
        assert "semantic_error" in types

    def test_deduplicates_services(self):
        events = make_events(services=["svc-a", "svc-a", "svc-a"])
        services, _, _ = _extract_event_facts(events)
        assert services == {"svc-a"}


# ── _check_services_grounding ─────────────────────────────────────────────────

class TestCheckServicesGrounding:

    def test_all_services_grounded(self):
        ratio, ungrounded = _check_services_grounding(
            ["checkout-api"], {"checkout-api", "payment-service"}
        )
        assert ratio == 1.0
        assert ungrounded == []

    def test_partial_services_grounded(self):
        ratio, ungrounded = _check_services_grounding(
            ["real-service", "invented-service"], {"real-service"}
        )
        assert ratio == 0.5
        assert "invented-service" in ungrounded

    def test_no_services_grounded(self):
        ratio, ungrounded = _check_services_grounding(
            ["ghost-svc"], {"real-svc"}
        )
        assert ratio == 0.0
        assert "ghost-svc" in ungrounded

    def test_empty_services_affected_returns_one(self):
        ratio, ungrounded = _check_services_grounding([], {"real-svc"})
        assert ratio == 1.0
        assert ungrounded == []

    def test_ungrounded_count_matches(self):
        ratio, ungrounded = _check_services_grounding(
            ["a", "b", "c"], {"a"}
        )
        assert len(ungrounded) == 2
        assert ratio == pytest.approx(1 / 3)


# ── _check_incident_types_grounding ──────────────────────────────────────────

class TestCheckIncidentTypesGrounding:

    def test_all_types_grounded(self):
        result = make_batch_result(
            events_by_service=[
                BatchEventSummary(
                    service="s", count=1,
                    dominant_severity="high",
                    incident_types=["technical_error"],
                )
            ]
        )
        ratio, ungrounded = _check_incident_types_grounding(
            result, {"technical_error"}
        )
        assert ratio == 1.0
        assert ungrounded == []

    def test_partial_types_grounded(self):
        result = make_batch_result(
            events_by_service=[
                BatchEventSummary(
                    service="s", count=2,
                    dominant_severity="medium",
                    incident_types=["technical_error", "invented_type"],
                )
            ]
        )
        ratio, ungrounded = _check_incident_types_grounding(
            result, {"technical_error"}
        )
        assert ratio == 0.5
        assert "invented_type" in ungrounded

    def test_no_types_in_events_by_service(self):
        result = make_batch_result(events_by_service=[])
        ratio, ungrounded = _check_incident_types_grounding(result, {"technical_error"})
        assert ratio == 1.0
        assert ungrounded == []

    def test_empty_incident_types_list(self):
        result = make_batch_result(
            events_by_service=[
                BatchEventSummary(
                    service="s", count=1,
                    dominant_severity="low",
                    incident_types=[],  # empty list
                )
            ]
        )
        ratio, ungrounded = _check_incident_types_grounding(result, {"technical_error"})
        assert ratio == 1.0
        assert ungrounded == []


# ── _check_critical_pattern_grounding ────────────────────────────────────────

class TestCheckCriticalPatternGrounding:

    def test_none_returns_true(self):
        assert _check_critical_pattern_grounding(None, {"svc"}, {"type"}) is True

    def test_references_real_service(self):
        result = _check_critical_pattern_grounding(
            "Cascade failure in checkout-api", {"checkout-api"}, set()
        )
        assert result is True

    def test_references_real_incident_type(self):
        result = _check_critical_pattern_grounding(
            "High rate of schema_error events", set(), {"schema_error"}
        )
        assert result is True

    def test_ungrounded_pattern(self):
        result = _check_critical_pattern_grounding(
            "Database corruption in postgres-primary", {"checkout-api"}, {"technical_error"}
        )
        assert result is False

    def test_case_insensitive_match(self):
        result = _check_critical_pattern_grounding(
            "CHECKOUT-API is down", {"checkout-api"}, set()
        )
        assert result is True


# ── _check_severity_consistency ───────────────────────────────────────────────

class TestCheckSeverityConsistency:

    def test_critical_majority_with_urgent_language(self):
        severities = ["critical"] * 6 + ["low"] * 4
        result = _check_severity_consistency(
            "Critical failures require immediate action.", severities
        )
        assert result is True

    def test_critical_majority_without_urgent_language(self):
        severities = ["critical"] * 6 + ["low"] * 4
        result = _check_severity_consistency(
            "The system looks fine, minor issues detected.", severities
        )
        assert result is False

    def test_low_severity_with_urgent_language(self):
        severities = ["low"] * 10
        result = _check_severity_consistency(
            "Critical emergency requires immediate response!", severities
        )
        assert result is False

    def test_low_severity_without_urgent_language(self):
        severities = ["low"] * 10
        result = _check_severity_consistency(
            "System appears stable. No significant issues.", severities
        )
        assert result is True

    def test_ambiguous_range_returns_true(self):
        # 30% critical/high → ambiguous range (20-49%), benefit of doubt
        severities = ["critical"] * 3 + ["low"] * 7
        result = _check_severity_consistency(
            "Some issues detected.", severities
        )
        assert result is True

    def test_empty_severities_returns_true(self):
        assert _check_severity_consistency("anything", []) is True

    def test_urgent_keywords_detected(self):
        severities = ["critical"] * 6 + ["low"] * 4
        for kw in ("urgent", "immediate", "severe", "emergency"):
            assert _check_severity_consistency(
                f"This is {kw}.", severities
            ) is True


# ── _compute_rule_score ───────────────────────────────────────────────────────

class TestComputeRuleScore:

    def _make_checks(
        self,
        services: float = 1.0,
        types: float = 1.0,
        pattern: bool = True,
        severity: bool = True,
    ) -> FaithfulnessRuleChecks:
        return FaithfulnessRuleChecks(
            services_grounded_ratio=services,
            incident_types_grounded_ratio=types,
            critical_pattern_references_real_entity=pattern,
            severity_assessment_consistent=severity,
        )

    def test_perfect_score_is_100(self):
        checks = self._make_checks()
        assert _compute_rule_score(checks) == 100

    def test_zero_score_when_all_fail(self):
        checks = self._make_checks(services=0.0, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks) == 0

    def test_services_weight_is_40(self):
        checks = self._make_checks(services=0.0, types=0.0, pattern=False, severity=False)
        checks_with_services = self._make_checks(services=1.0, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks_with_services) - _compute_rule_score(checks) == 40

    def test_types_weight_is_30(self):
        checks_with_types = self._make_checks(services=0.0, types=1.0, pattern=False, severity=False)
        checks_without = self._make_checks(services=0.0, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks_with_types) - _compute_rule_score(checks_without) == 30

    def test_pattern_weight_is_10(self):
        checks_with = self._make_checks(services=0.0, types=0.0, pattern=True, severity=False)
        checks_without = self._make_checks(services=0.0, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks_with) - _compute_rule_score(checks_without) == 10

    def test_severity_weight_is_20(self):
        checks_with = self._make_checks(services=0.0, types=0.0, pattern=False, severity=True)
        checks_without = self._make_checks(services=0.0, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks_with) - _compute_rule_score(checks_without) == 20

    def test_partial_services(self):
        checks = self._make_checks(services=0.5, types=0.0, pattern=False, severity=False)
        assert _compute_rule_score(checks) == 20  # 0.5 * 40 = 20


# ── _verdict ──────────────────────────────────────────────────────────────────

class TestVerdict:

    def test_faithful_at_80(self):
        assert _verdict(80) == "faithful"

    def test_faithful_above_80(self):
        assert _verdict(95) == "faithful"

    def test_partially_faithful_at_40(self):
        assert _verdict(40) == "partially_faithful"

    def test_partially_faithful_at_79(self):
        assert _verdict(79) == "partially_faithful"

    def test_hallucinated_at_39(self):
        assert _verdict(39) == "hallucinated"

    def test_hallucinated_at_0(self):
        assert _verdict(0) == "hallucinated"


# ── evaluate_faithfulness — integration ──────────────────────────────────────

class TestEvaluateFaithfulness:

    def test_returns_faithfulness_result(self):
        result = evaluate_faithfulness(
            make_batch_result(), make_events()
        )
        assert isinstance(result, FaithfulnessResult)

    def test_batch_id_preserved(self):
        batch = make_batch_result(batch_id="batch_abc123")
        result = evaluate_faithfulness(batch, make_events())
        assert result.batch_id == "batch_abc123"

    def test_evaluated_at_is_set(self):
        result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.evaluated_at != ""
        assert "T" in result.evaluated_at  # ISO 8601 format

    def test_score_in_range(self):
        result = evaluate_faithfulness(make_batch_result(), make_events())
        assert 0 <= result.faithfulness_score <= 100

    def test_verdict_is_valid_literal(self):
        result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.verdict in ("faithful", "partially_faithful", "hallucinated")

    def test_all_grounded_yields_high_score(self):
        batch = make_batch_result(
            services_affected=["checkout-api"],
            overall_assessment="High severity issues in checkout-api require immediate attention.",
            critical_pattern="checkout-api failures",
            events_by_service=[
                BatchEventSummary(
                    service="checkout-api",
                    count=5,
                    dominant_severity="critical",
                    incident_types=["technical_error"],
                )
            ],
        )
        events = make_events(
            services=["checkout-api"] * 5,
            incident_types=["technical_error"] * 5,
            severities=["critical"] * 5,
        )
        result = evaluate_faithfulness(batch, events)
        assert result.faithfulness_score >= 80
        assert result.verdict == "faithful"

    def test_invented_service_reduces_score(self):
        batch = make_batch_result(
            services_affected=["checkout-api", "ghost-service"],
        )
        events = make_events(services=["checkout-api"])
        result = evaluate_faithfulness(batch, events)
        # services_grounded_ratio = 0.5 → 20 pts instead of 40 → score < 100
        assert result.faithfulness_score < 100

    def test_invented_service_in_ungrounded_claims(self):
        batch = make_batch_result(
            services_affected=["checkout-api", "ghost-service"],
        )
        events = make_events(services=["checkout-api"])
        result = evaluate_faithfulness(batch, events)
        claims_text = " ".join(result.ungrounded_claims)
        assert "ghost-service" in claims_text

    def test_invented_incident_type_reduces_score(self):
        batch = make_batch_result(
            events_by_service=[
                BatchEventSummary(
                    service="checkout-api",
                    count=2,
                    dominant_severity="high",
                    incident_types=["technical_error", "invented_type"],
                )
            ]
        )
        events = make_events(incident_types=["technical_error"])
        result = evaluate_faithfulness(batch, events)
        assert result.faithfulness_score < 100

    def test_ungrounded_critical_pattern_in_claims(self):
        batch = make_batch_result(
            critical_pattern="ghost-database corruption detected"
        )
        events = make_events(services=["checkout-api"])
        result = evaluate_faithfulness(batch, events)
        claims_text = " ".join(result.ungrounded_claims)
        assert "critical_pattern" in claims_text

    def test_no_llm_without_key(self):
        # no_openai_key fixture removes OPENAI_API_KEY
        result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.llm_used is False

    def test_empty_events_returns_result(self):
        batch = make_batch_result()
        result = evaluate_faithfulness(batch, [])
        # Empty events → ungrounded (services_affected not in empty set)
        assert result.faithfulness_score < 100

    def test_empty_services_affected(self):
        batch = make_batch_result(services_affected=[])
        result = evaluate_faithfulness(batch, make_events())
        # services_grounded_ratio = 1.0 (vacuously true)
        checks = result.rule_checks
        assert checks.services_grounded_ratio == 1.0

    def test_rule_checks_are_present(self):
        result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.rule_checks is not None
        assert hasattr(result.rule_checks, "services_grounded_ratio")
        assert hasattr(result.rule_checks, "severity_assessment_consistent")

    def test_severity_overreport_flagged(self):
        batch = make_batch_result(
            overall_assessment="Critical emergency! Immediate action required!",
        )
        # All events are low severity
        events = make_events(severities=["low"] * 10)
        result = evaluate_faithfulness(batch, events)
        assert not result.rule_checks.severity_assessment_consistent
        claims_text = " ".join(result.ungrounded_claims)
        assert "severity" in claims_text


# ── evaluate_faithfulness — LLM judge mock ───────────────────────────────────

class TestEvaluateFaithfulnessWithLLM:

    def _mock_judge(self, response_content: dict) -> MagicMock:
        mock_cls = MagicMock()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_judge_response(
            response_content["faithfulness_score"],
            response_content["ungrounded_claims"],
            response_content["verdict"],
        )
        return mock_cls

    def test_llm_used_true_when_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        judge_mock = self._mock_judge(
            {"faithfulness_score": 90, "ungrounded_claims": [], "verdict": "faithful"}
        )
        with patch("openai.OpenAI", judge_mock):
            result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.llm_used is True

    def test_llm_score_averaged_with_rule_score(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        # A batch result that scores 100 rule-based
        batch = make_batch_result(
            services_affected=["checkout-api"],
            overall_assessment="Immediate critical failures in checkout-api.",
            critical_pattern="checkout-api cascade",
            events_by_service=[
                BatchEventSummary(
                    service="checkout-api",
                    count=5,
                    dominant_severity="critical",
                    incident_types=["technical_error"],
                )
            ],
        )
        events = make_events(
            services=["checkout-api"] * 5,
            incident_types=["technical_error"] * 5,
            severities=["critical"] * 5,
        )
        judge_mock = self._mock_judge(
            {"faithfulness_score": 60, "ungrounded_claims": [], "verdict": "partially_faithful"}
        )
        with patch("openai.OpenAI", judge_mock):
            result = evaluate_faithfulness(batch, events)
        # rule_score = 100, llm_score = 60 → final = (100+60)//2 = 80
        assert result.faithfulness_score == 80

    def test_llm_claims_override_empty_rule_claims(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        judge_mock = self._mock_judge(
            {
                "faithfulness_score": 50,
                "ungrounded_claims": ["LLM spotted this claim"],
                "verdict": "partially_faithful",
            }
        )
        with patch("openai.OpenAI", judge_mock):
            result = evaluate_faithfulness(make_batch_result(), make_events())
        assert "LLM spotted this claim" in result.ungrounded_claims

    def test_llm_fallback_on_exception(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_cls = MagicMock()
        mock_cls.side_effect = RuntimeError("OpenAI exploded")
        with patch("openai.OpenAI", mock_cls):
            # Should not raise — falls back to rule-based
            result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.llm_used is False
        assert isinstance(result.faithfulness_score, int)

    def test_llm_invalid_verdict_replaced(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        judge_mock = self._mock_judge(
            {
                "faithfulness_score": 88,
                "ungrounded_claims": [],
                "verdict": "INVALID_VERDICT",
            }
        )
        with patch("openai.OpenAI", judge_mock):
            result = evaluate_faithfulness(make_batch_result(), make_events())
        # verdict should be derived from score, not the invalid string
        assert result.verdict in ("faithful", "partially_faithful", "hallucinated")

    def test_llm_score_clamped_to_100(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        judge_mock = self._mock_judge(
            {"faithfulness_score": 150, "ungrounded_claims": [], "verdict": "faithful"}
        )
        with patch("openai.OpenAI", judge_mock):
            result = evaluate_faithfulness(make_batch_result(), make_events())
        assert result.faithfulness_score <= 100
