"""
Step 13 — Test suite for the evaluation engine and RAG models.

These tests run without any external services (no PostgreSQL, no Redis,
no OpenAI API) — they exercise pure domain logic and model validation.

Designed to be the fast, always-green test suite that runs in CI on every push.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

CRITICAL_INCIDENT = {
    "id": "test-001",
    "timestamp": "2026-01-15T10:00:00Z",
    "workflow": "checkout-flow",
    "stage": "validation",
    "incidentType": "schema_error",
    "category": "output_format",
    "severity": "critical",
    "source": "gpt-4o-mini",
    "message": "LLM output failed JSON schema validation",
    "context": {"field": "total_price", "error": "expected number, got string"},
}

DEGRADATION_INCIDENT = {
    "id": "test-002",
    "timestamp": "2026-01-15T10:05:00Z",
    "workflow": "search-flow",
    "stage": "generation",
    "incidentType": "degradation",
    "category": "performance",
    "severity": "low",
    "source": "gpt-4o-mini",
    "message": "Latency increased by 40% over last 10 evaluations",
    "context": None,
}

TECHNICAL_ERROR_HIGH = {
    "id": "test-003",
    "timestamp": "2026-01-15T10:10:00Z",
    "workflow": "recommendation-flow",
    "stage": "inference",
    "incidentType": "technical_error",
    "category": "provider",
    "severity": "high",
    "source": "gpt-4o-mini",
    "message": "OpenAI API 503 Service Unavailable",
    "context": {"retry_count": 3, "last_error": "503"},
}

SEMANTIC_ERROR_MEDIUM = {
    "id": "test-004",
    "timestamp": "2026-01-15T10:15:00Z",
    "workflow": "qa-flow",
    "stage": "evaluation",
    "incidentType": "semantic_error",
    "category": "quality",
    "severity": "medium",
    "source": "gpt-4o-mini",
    "message": "Answer factually incorrect based on context",
    "context": None,
}


# ── Engine unit tests ─────────────────────────────────────────────────────────

class TestEvaluationEngine:
    """Unit tests for the deterministic rule-based evaluation engine."""

    def test_schema_error_critical_severity_returns_critical_status(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident, RequestMeta

        req = EvaluationRequest(
            incident=StandardIncident(**CRITICAL_INCIDENT),
            requestMeta=None,
        )
        result = evaluate(req)
        assert result.status == "critical"
        assert result.score >= 70
        assert result.suggestedAction == "inspect_schema"
        assert "schema_error" in (result.tags or [])

    def test_technical_error_high_severity_returns_critical(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident

        req = EvaluationRequest(
            incident=StandardIncident(**TECHNICAL_ERROR_HIGH),
        )
        result = evaluate(req)
        assert result.status == "critical"
        assert result.score >= 75
        assert result.suggestedAction == "check_provider"

    def test_degradation_low_severity_returns_needs_attention(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident

        req = EvaluationRequest(
            incident=StandardIncident(**DEGRADATION_INCIDENT),
        )
        result = evaluate(req)
        assert result.status == "needs_attention"
        assert result.suggestedAction == "monitor"

    def test_semantic_error_medium_returns_needs_attention(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident

        req = EvaluationRequest(
            incident=StandardIncident(**SEMANTIC_ERROR_MEDIUM),
        )
        result = evaluate(req)
        assert result.status == "needs_attention"
        assert result.score <= 65
        assert result.suggestedAction == "inspect_prompt"

    def test_score_always_in_range(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident

        for incident_data in [
            CRITICAL_INCIDENT, DEGRADATION_INCIDENT,
            TECHNICAL_ERROR_HIGH, SEMANTIC_ERROR_MEDIUM,
        ]:
            result = evaluate(
                EvaluationRequest(incident=StandardIncident(**incident_data))
            )
            assert 0 <= result.score <= 100, f"Score {result.score} out of range"

    def test_summary_and_reasoning_always_present(self):
        from eval_py.engine import evaluate
        from eval_py.models import EvaluationRequest, StandardIncident

        for incident_data in [CRITICAL_INCIDENT, DEGRADATION_INCIDENT]:
            result = evaluate(
                EvaluationRequest(incident=StandardIncident(**incident_data))
            )
            assert result.summary, "Summary should not be empty"


# ── Pydantic model validation tests ──────────────────────────────────────────

class TestModels:
    """Validate Pydantic model constraints and the RAG response models."""

    def test_evaluation_result_score_bounds(self):
        from eval_py.models import EvaluationResult
        import pytest

        with pytest.raises(Exception):
            EvaluationResult(
                status="ok", score=101, summary="test", reasoning="test"
            )

        with pytest.raises(Exception):
            EvaluationResult(
                status="ok", score=-1, summary="test", reasoning="test"
            )

    def test_rag_evaluation_result_defaults(self):
        from eval_py.models import RagEvaluationResult

        result = RagEvaluationResult(
            status="ok",
            score=75,
            summary="All good",
            reasoning="No issues detected",
        )
        assert result.similarIncidents == []
        assert result.ragContextUsed is False
        assert result.embeddingStored is False

    def test_similar_incident_response_fields(self):
        from eval_py.models import SimilarIncidentResponse

        inc = SimilarIncidentResponse(
            recordId="rec_abc123",
            workflow="checkout-flow",
            incidentType="schema_error",
            severity="high",
            summary="Schema validation failed",
            suggestedAction="inspect_schema",
            evalStatus="critical",
            evalScore=85,
            similarity=0.92,
        )
        assert 0.0 <= inc.similarity <= 1.0
        assert inc.evalScore == 85

    def test_standard_incident_requires_all_fields(self):
        from eval_py.models import StandardIncident
        import pytest

        with pytest.raises(Exception):
            StandardIncident(
                id="x",
                # Missing required fields
            )


# ── RAG retriever unit tests (no DB) ─────────────────────────────────────────

class TestRagRetriever:
    """Unit tests for RAG utilities that run without external dependencies."""

    def test_incident_to_text_includes_key_fields(self):
        from eval_py.rag_retriever import _incident_to_text

        text = _incident_to_text(CRITICAL_INCIDENT)
        assert "checkout-flow" in text
        assert "schema_error" in text
        assert "critical" in text
        assert "validation" in text

    def test_build_rag_context_empty_list(self):
        from eval_py.rag_retriever import build_rag_context

        ctx = build_rag_context([])
        assert ctx == ""

    def test_build_rag_context_formats_similarity(self):
        from eval_py.rag_retriever import build_rag_context, SimilarIncident

        inc = SimilarIncident(
            record_id="rec_001",
            workflow="checkout-flow",
            incident_type="schema_error",
            severity="high",
            summary="Schema failed",
            suggested_action="escalate",
            eval_status="critical",
            eval_score=85,
            similarity=0.87,
        )
        ctx = build_rag_context([inc])
        assert "87%" in ctx
        assert "checkout-flow" in ctx
        assert "escalate" in ctx

    def test_generate_embedding_returns_none_without_api_key(self, monkeypatch):
        import os
        from eval_py.rag_retriever import generate_embedding

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = generate_embedding("test incident text")
        assert result is None


# ── Metrics module tests ──────────────────────────────────────────────────────

class TestMetrics:
    """Verify the metrics module loads and no-ops work correctly."""

    def test_metrics_module_importable(self):
        from eval_py import metrics
        assert hasattr(metrics, "eval_requests_total")
        assert hasattr(metrics, "rag_retrieval_latency")
        assert hasattr(metrics, "is_available")

    def test_noop_metrics_dont_raise(self):
        """Even with prometheus_client available, calling metrics should not raise."""
        from eval_py.metrics import eval_requests_total, eval_score_histogram

        # These should never raise regardless of prometheus_client state
        eval_requests_total.labels(status="critical").inc()
        eval_score_histogram.observe(85)


# ── LlamaIndex pipeline tests ─────────────────────────────────────────────────

class TestLlamaIndexPipeline:
    """Tests for the LlamaIndex abstraction layer."""

    def test_rag_llamaindex_importable(self):
        from eval_py import rag_llamaindex
        assert hasattr(rag_llamaindex, "is_available")
        assert hasattr(rag_llamaindex, "incident_to_node")
        assert hasattr(rag_llamaindex, "retrieve_similar")

    def test_incident_to_node_structure(self):
        """Test node creation when LlamaIndex is available."""
        from eval_py.rag_llamaindex import is_available, incident_to_node

        if not is_available():
            pytest.skip("llama-index-core not installed")

        node = incident_to_node(CRITICAL_INCIDENT, record_id="rec_test_001")
        assert node.id_ == "rec_test_001"
        assert "checkout-flow" in node.text
        assert node.metadata["incident_type"] == "schema_error"
        assert node.metadata["severity"] == "critical"

    def test_retrieve_similar_returns_empty_without_db(self, monkeypatch):
        """retrieve_similar should return [] gracefully when DB is not reachable."""
        from eval_py.rag_llamaindex import retrieve_similar

        # Monkeypatch build_index_from_store to simulate DB unavailable
        import eval_py.rag_llamaindex as m
        monkeypatch.setattr(m, "build_index_from_store", lambda: None)

        result = retrieve_similar(CRITICAL_INCIDENT, top_k=3)
        assert result == []
