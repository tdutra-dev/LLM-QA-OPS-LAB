"""
test_batch_analyzer.py — Test suite per il batch analyzer (Fase 3).

Cosa testiamo:
- _build_user_prompt(): formato corretto, N eventi, window_seconds
- run_batch_analysis([]) → empty BatchAnalysisResult (event_count=0, llm_used=False)
- run_batch_analysis senza OPENAI_API_KEY → fallback rule-based
- run_batch_analysis con mock OpenAI → parsa risposta strutturata correctamente
- _build_fallback_result(): alta concentrazione critica → assessment corretto
- hallucination_risk e confidence_score nel risultato LLM
- Graceful degradation: OpenAI raise → fallback rule-based
- JSON malformato da LLM → fallback senza eccezione

Nessuna dipendenza esterna — OpenAI viene sempre mockato o aggirato.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from eval_py.batch_analyzer import (
    _build_fallback_result,
    _build_user_prompt,
    run_batch_analysis,
)
from eval_py.models import BatchAnalysisResult, BatchEventSummary


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_events(
    n: int = 3,
    service: str = "checkout-api",
    severity: str = "high",
    incident_type: str = "technical_error",
) -> list[dict]:
    return [
        {
            "incident_id": f"inc-{i:03d}",
            "source_system": "spring-boot",
            "service": service,
            "severity": severity,
            "message": f"Error {i} in {service}",
            "incident_type": incident_type,
        }
        for i in range(n)
    ]


def _make_openai_response(content: dict) -> MagicMock:
    """Simula un oggetto response di OpenAI chat.completions.create."""
    response = MagicMock()
    response.choices[0].message.content = json.dumps(content)
    return response


VALID_LLM_RESPONSE = {
    "overall_assessment": "Critical failures detected across checkout-api service.",
    "critical_pattern": "Repeated NullPointerException in payment processing",
    "recommended_actions": ["Rollback last deployment", "Check DB connections"],
    "events_by_service": [
        {
            "service": "checkout-api",
            "count": 3,
            "dominant_severity": "high",
            "incident_types": ["technical_error"],
        }
    ],
    "hallucination_risk": "low",
    "confidence_score": 85,
}


# ── _build_user_prompt ────────────────────────────────────────────────────────

class TestBuildUserPrompt:

    def test_includes_event_count(self):
        events = make_events(5)
        prompt = _build_user_prompt(events, window_seconds=300)
        assert "5 incident" in prompt

    def test_includes_window_minutes(self):
        prompt = _build_user_prompt(make_events(1), window_seconds=300)
        assert "5 minutes" in prompt

    def test_includes_each_service(self):
        events = make_events(2, service="payment-service")
        prompt = _build_user_prompt(events, window_seconds=60)
        assert "payment-service" in prompt

    def test_includes_severity(self):
        events = make_events(1, severity="critical")
        prompt = _build_user_prompt(events, window_seconds=300)
        assert "severity=critical" in prompt

    def test_includes_incident_type(self):
        events = make_events(1, incident_type="schema_error")
        prompt = _build_user_prompt(events, window_seconds=300)
        assert "type=schema_error" in prompt

    def test_message_truncated_to_120_chars(self):
        events = [{"service": "x", "severity": "low", "message": "A" * 200, "incident_type": "t"}]
        prompt = _build_user_prompt(events, window_seconds=300)
        # Il messaggio nel prompt non deve superare 120 'A'
        assert "A" * 121 not in prompt

    def test_handles_empty_events(self):
        prompt = _build_user_prompt([], window_seconds=300)
        assert "0 incident" in prompt

    def test_numbered_list(self):
        events = make_events(3)
        prompt = _build_user_prompt(events, window_seconds=300)
        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt


# ── run_batch_analysis: empty input ──────────────────────────────────────────

class TestRunBatchAnalysisEmpty:

    def test_empty_events_returns_empty_result(self):
        result = run_batch_analysis([], window_seconds=300)
        assert isinstance(result, BatchAnalysisResult)
        assert result.event_count == 0
        assert result.llm_used is False
        assert result.services_affected == []
        assert result.events_by_service == []

    def test_empty_events_confidence_is_zero(self):
        result = run_batch_analysis([])
        assert result.confidence_score == 0

    def test_empty_events_hallucination_risk_is_low(self):
        result = run_batch_analysis([])
        assert result.hallucination_risk == "low"

    def test_empty_events_no_openai_call(self):
        with patch("openai.OpenAI") as mock_openai:
            run_batch_analysis([])
            mock_openai.assert_not_called()


# ── run_batch_analysis: no API key → fallback ─────────────────────────────────

class TestRunBatchAnalysisFallback:

    @pytest.fixture(autouse=True)
    def no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def test_returns_batch_analysis_result(self):
        result = run_batch_analysis(make_events(3))
        assert isinstance(result, BatchAnalysisResult)

    def test_llm_used_is_false(self):
        result = run_batch_analysis(make_events(3))
        assert result.llm_used is False

    def test_event_count_matches_input(self):
        result = run_batch_analysis(make_events(5))
        assert result.event_count == 5

    def test_window_seconds_preserved(self):
        result = run_batch_analysis(make_events(3), window_seconds=600)
        assert result.window_seconds == 600

    def test_services_affected_contains_input_service(self):
        result = run_batch_analysis(make_events(3, service="checkout-api"))
        assert "checkout-api" in result.services_affected

    def test_events_by_service_aggregated_correctly(self):
        events = make_events(4, service="payment-api", severity="critical")
        result = run_batch_analysis(events)
        assert len(result.events_by_service) == 1
        svc = result.events_by_service[0]
        assert svc.service == "payment-api"
        assert svc.count == 4
        assert svc.dominant_severity == "critical"

    def test_multi_service_events(self):
        events = make_events(2, service="checkout") + make_events(2, service="payment")
        result = run_batch_analysis(events)
        services = {s.service for s in result.events_by_service}
        assert "checkout" in services
        assert "payment" in services

    def test_overall_assessment_not_empty(self):
        result = run_batch_analysis(make_events(3))
        assert result.overall_assessment
        assert len(result.overall_assessment) > 10

    def test_hallucination_risk_is_low(self):
        """Rule-based = nessuna allucinazione."""
        result = run_batch_analysis(make_events(3))
        assert result.hallucination_risk == "low"

    def test_no_openai_call_made(self):
        with patch("openai.OpenAI") as mock_cls:
            run_batch_analysis(make_events(3))
            mock_cls.assert_not_called()


# ── _build_fallback_result: assessment logic ──────────────────────────────────

class TestBuildFallbackResult:

    def test_majority_critical_produces_critical_assessment(self):
        """Più del 50% critical/high → assessment urgente."""
        events = [
            {"service": "api", "severity": "critical", "message": "x"},
            {"service": "api", "severity": "critical", "message": "y"},
            {"service": "api", "severity": "low", "message": "z"},
        ]
        result = _build_fallback_result(events, window_seconds=300)
        assert "critical" in result.overall_assessment.lower() or "immediate" in result.overall_assessment.lower()
        assert result.critical_pattern is not None
        assert len(result.recommended_actions) >= 2

    def test_majority_low_severity_no_critical_pattern(self):
        events = [
            {"service": "api", "severity": "low", "message": "x"},
            {"service": "api", "severity": "low", "message": "y"},
        ]
        result = _build_fallback_result(events, window_seconds=300)
        assert result.critical_pattern is None

    def test_empty_events_produces_no_action_result(self):
        result = _build_fallback_result([], window_seconds=300)
        assert result.event_count == 0
        assert result.recommended_actions == []

    def test_dominant_severity_is_max_rank(self):
        """dominant_severity deve essere il più grave tra gli eventi del service."""
        events = [
            {"service": "api", "severity": "low", "message": "x"},
            {"service": "api", "severity": "critical", "message": "y"},
            {"service": "api", "severity": "medium", "message": "z"},
        ]
        result = _build_fallback_result(events, window_seconds=300)
        assert result.events_by_service[0].dominant_severity == "critical"

    def test_batch_id_is_generated(self):
        result = _build_fallback_result(make_events(2), window_seconds=300)
        assert result.batch_id.startswith("batch_")

    def test_confidence_score_40_when_events_present(self):
        result = _build_fallback_result(make_events(3), window_seconds=300)
        assert result.confidence_score == 40


# ── run_batch_analysis: with mock OpenAI ──────────────────────────────────────

class TestRunBatchAnalysisWithLLM:

    @pytest.fixture(autouse=True)
    def set_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-fake")

    def _mock_openai(self, response_content: dict):
        mock_cls = MagicMock()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response(
            response_content
        )
        return mock_cls

    def test_llm_used_is_true(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.llm_used is True

    def test_overall_assessment_from_llm(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.overall_assessment == VALID_LLM_RESPONSE["overall_assessment"]

    def test_critical_pattern_from_llm(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.critical_pattern == VALID_LLM_RESPONSE["critical_pattern"]

    def test_recommended_actions_from_llm(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.recommended_actions == VALID_LLM_RESPONSE["recommended_actions"]

    def test_hallucination_risk_from_llm(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.hallucination_risk == "low"

    def test_confidence_score_from_llm(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.confidence_score == 85

    def test_events_by_service_parsed(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert len(result.events_by_service) == 1
        svc = result.events_by_service[0]
        assert isinstance(svc, BatchEventSummary)
        assert svc.service == "checkout-api"
        assert svc.count == 3

    def test_raw_llm_response_preserved(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(3))
        assert result.raw_llm_response is not None
        parsed = json.loads(result.raw_llm_response)
        assert parsed["confidence_score"] == 85

    def test_invalid_hallucination_risk_normalized_to_medium(self):
        bad_response = {**VALID_LLM_RESPONSE, "hallucination_risk": "extreme"}
        with patch("openai.OpenAI", self._mock_openai(bad_response)):
            result = run_batch_analysis(make_events(3))
        assert result.hallucination_risk == "medium"

    def test_confidence_score_clamped_to_0_100(self):
        bad_response = {**VALID_LLM_RESPONSE, "confidence_score": 150}
        with patch("openai.OpenAI", self._mock_openai(bad_response)):
            result = run_batch_analysis(make_events(3))
        assert result.confidence_score == 100

    def test_openai_exception_falls_back_to_rule_based(self):
        mock_cls = MagicMock()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error 500")

        with patch("openai.OpenAI", mock_cls):
            result = run_batch_analysis(make_events(3))

        assert result.llm_used is False
        assert isinstance(result, BatchAnalysisResult)

    def test_malformed_json_from_llm_falls_back_to_rule_based(self):
        mock_cls = MagicMock()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "not valid json at all {"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", mock_cls):
            result = run_batch_analysis(make_events(3))

        assert result.llm_used is False

    def test_event_count_always_matches_input(self):
        with patch("openai.OpenAI", self._mock_openai(VALID_LLM_RESPONSE)):
            result = run_batch_analysis(make_events(7))
        assert result.event_count == 7
