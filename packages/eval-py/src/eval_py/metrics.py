"""
Step 12 — Prometheus Metrics: custom application-level observability.

Architecture
────────────
This module defines all custom Prometheus metrics for the LLM-QA-OPS evaluation
service. It works in two layers:

    1. AUTOMATIC (via prometheus-fastapi-instrumentator):
       - http_requests_total         — per endpoint, method, status code
       - http_request_duration_seconds — latency histograms (p50/p95/p99)
       These are registered and exposed by instrument_app() in main.py.

    2. CUSTOM (defined here):
       - eval_requests_total         — evaluation counter by status
       - eval_score_histogram         — distribution of evaluation scores
       - rag_retrieval_latency_seconds — time spent on pgvector similarity search
       - rag_embedding_latency_seconds — time spent on OpenAI embedding call
       - rag_similar_incidents_found  — how many similar incidents were retrieved
       - agent_loop_iterations_total  — agent loop cycle counter
       - action_executor_total        — actions dispatched by type + outcome

Usage in endpoints
──────────────────
    from .metrics import eval_requests_total, eval_score_histogram
    eval_requests_total.labels(status="critical").inc()
    eval_score_histogram.observe(result.score)

The /metrics endpoint is exposed by Prometheus-FastAPI-Instrumentator in main.py.
Scraping interval: Prometheus is configured to scrape every 15s (see docker-compose.yml).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Lazy registry ──────────────────────────────────────────────────────────────
# We import prometheus_client only when used so the service doesn't crash if
# the package is not yet installed (graceful degradation during local dev).
try:
    from prometheus_client import Counter, Histogram

    # ── Evaluation metrics ────────────────────────────────────────────────────

    eval_requests_total = Counter(
        "llmqa_eval_requests_total",
        "Total evaluation requests processed, labelled by result status.",
        labelnames=["status"],        # ok | needs_attention | critical
    )

    eval_score_histogram = Histogram(
        "llmqa_eval_score",
        "Distribution of evaluation scores (0–100).",
        buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    )

    # ── RAG metrics ───────────────────────────────────────────────────────────

    rag_retrieval_latency = Histogram(
        "llmqa_rag_retrieval_latency_seconds",
        "Time spent executing the pgvector similarity search query.",
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )

    rag_embedding_latency = Histogram(
        "llmqa_rag_embedding_latency_seconds",
        "Time spent calling OpenAI to generate the query embedding.",
        buckets=[0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0],
    )

    rag_similar_found = Histogram(
        "llmqa_rag_similar_incidents_found",
        "Number of similar incidents retrieved per RAG evaluation.",
        buckets=[0, 1, 2, 3, 4, 5],
    )

    rag_requests_total = Counter(
        "llmqa_rag_requests_total",
        "Total RAG-augmented evaluation requests, labelled by retrieval outcome.",
        labelnames=["retrieval"],     # hit | miss (miss = 0 similar found)
    )

    # ── Agent loop metrics ────────────────────────────────────────────────────

    agent_loop_iterations_total = Counter(
        "llmqa_agent_loop_iterations_total",
        "Total agent loop cycle iterations executed.",
    )

    agent_loop_errors_total = Counter(
        "llmqa_agent_loop_errors_total",
        "Total unhandled errors inside the agent loop cycle.",
    )

    # ── Action executor metrics ───────────────────────────────────────────────

    action_executor_total = Counter(
        "llmqa_action_executor_total",
        "Total actions dispatched by the ActionExecutor.",
        labelnames=["action_type", "outcome"],  # restart | scale | alert | ... | success | skipped | error
    )

    _metrics_available = True
    logger.info("[metrics] Prometheus custom metrics registered successfully")

except ImportError:
    # prometheus_client not installed — define no-op stubs so imports don't fail
    logger.warning(
        "[metrics] prometheus_client not installed — metrics are disabled. "
        "Run: pip install prometheus-client prometheus-fastapi-instrumentator"
    )

    class _NoOp:
        """No-op stub that silently ignores all metric operations."""
        def labels(self, **_):  # type: ignore[no-untyped-def]
            return self
        def inc(self, *_, **__):  # type: ignore[no-untyped-def]
            pass
        def observe(self, *_, **__):  # type: ignore[no-untyped-def]
            pass
        def set(self, *_, **__):  # type: ignore[no-untyped-def]
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    _noop = _NoOp()
    eval_requests_total = _noop          # type: ignore[assignment]
    eval_score_histogram = _noop         # type: ignore[assignment]
    rag_retrieval_latency = _noop        # type: ignore[assignment]
    rag_embedding_latency = _noop        # type: ignore[assignment]
    rag_similar_found = _noop            # type: ignore[assignment]
    rag_requests_total = _noop           # type: ignore[assignment]
    agent_loop_iterations_total = _noop  # type: ignore[assignment]
    agent_loop_errors_total = _noop      # type: ignore[assignment]
    action_executor_total = _noop        # type: ignore[assignment]

    _metrics_available = False


def is_available() -> bool:
    """Return True if prometheus_client is installed and metrics are active."""
    return _metrics_available
