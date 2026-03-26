"""
Step 8 — IncidentGenerator: simulated incident stream for the Agent Loop.

Role in the agentic architecture
─────────────────────────────────
In a real production system the incident stream comes from an external source:
  - A Kafka / SQS topic populated by the LLM gateway
  - A Prometheus alert webhook
  - A PostgreSQL table polled with LISTEN/NOTIFY

For the Agent Loop demo we simulate this stream deterministically:
every call to `generate()` returns a plausible `EvaluationRequest` drawn
from a realistic pool of workflows, stages, error types, and severities.

The generator uses Python's standard `random` module seeded per-call so
the stream is varied but reproducible for unit tests when a fixed seed is
supplied.

Extending for production
─────────────────────────
Replace `generate()` with an async version that reads from your queue:

    async def generate() -> EvaluationRequest | None:
        msg = await sqs_client.receive_message(QueueUrl=INCIDENT_QUEUE_URL)
        if not msg:
            return None
        payload = json.loads(msg["Body"])
        return EvaluationRequest.model_validate(payload)

The Agent Loop calls `generate()` once per cycle and handles `None` (nothing
in the queue) by skipping the evaluation step gracefully.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from uuid import uuid4

from .models import EvaluationRequest, StandardIncident

# ── Incident pools ─────────────────────────────────────────────────────────────

_WORKFLOWS = [
    "checkout",
    "product-description",
    "customer-support",
    "fraud-detection",
    "recommendation-engine",
    "invoice-processing",
    "search-ranking",
]

_STAGES: dict[str, list[str]] = {
    "checkout":               ["payment-llm", "validation", "confirmation-gen"],
    "product-description":    ["description-gen", "tone-check", "seo-enhance"],
    "customer-support":       ["intent-classify", "response-gen", "sentiment-check"],
    "fraud-detection":        ["feature-extract", "risk-score", "decision-llm"],
    "recommendation-engine":  ["embedding-gen", "similarity-rank", "explanation-gen"],
    "invoice-processing":     ["ocr-parse", "field-extract", "validation-llm"],
    "search-ranking":         ["query-expand", "relevance-score", "snippet-gen"],
}

_SOURCES = ["openai", "anthropic", "mistral", "azure-oai", "bedrock"]

_INCIDENT_TYPES = [
    "technical_error",
    "schema_error",
    "semantic_error",
    "degradation",
]

# Map incident type → realistic example messages
_MESSAGES: dict[str, list[str]] = {
    "technical_error": [
        "Request timed out after 30 s — provider did not respond",
        "HTTP 503 received from LLM endpoint — service temporarily unavailable",
        "Connection reset by peer during streaming response",
        "Rate limit exceeded: 429 Too Many Requests",
    ],
    "schema_error": [
        "Output JSON missing required field 'confidence_score'",
        "Response array contained null items where objects were expected",
        "Unexpected key 'debug_trace' in production response schema",
        "Enum value 'UNCERTAIN' not in allowed set ['YES', 'NO', 'MAYBE']",
    ],
    "semantic_error": [
        "LLM returned a payment confirmation for an order that was never placed",
        "Product description contradicts listed specifications (wool coat → cotton)",
        "Customer support response addressed unrelated topic (billing vs. shipping)",
        "Recommendation explanation referenced items not in the candidate set",
    ],
    "degradation": [
        "Average response quality score dropped 18 pp vs. 7-day baseline",
        "P95 latency increased to 12.3 s — SLA breach threshold is 8 s",
        "Semantic similarity score: 0.51 — below acceptance threshold of 0.70",
        "Error rate in workflow rose from 1.2% to 9.7% over last 2 hours",
    ],
}

# Map incident type → plausible category tags
_CATEGORIES: dict[str, list[str]] = {
    "technical_error": ["connectivity", "timeout", "rate_limit", "infra"],
    "schema_error":    ["output_format", "contract_violation", "parsing"],
    "semantic_error":  ["output_quality", "hallucination", "accuracy"],
    "degradation":     ["performance", "quality_drift", "latency", "reliability"],
}

_SEVERITIES = ["low", "medium", "high", "critical"]

# Weight toward lower severities so critical is rare (mimics real distributions)
_SEVERITY_WEIGHTS = [0.35, 0.35, 0.20, 0.10]


# ── Public API ─────────────────────────────────────────────────────────────────

def generate(rng: random.Random | None = None) -> EvaluationRequest:
    """
    Generate a single synthetic incident as an `EvaluationRequest`.

    Parameters
    ----------
    rng:
        Optional `random.Random` instance for reproducible generation in tests.
        If None, uses module-level random state (non-deterministic).

    Returns
    -------
    EvaluationRequest
        A fully-populated request ready to pass to `evaluate()`.
    """
    r = rng or random

    workflow = r.choice(_WORKFLOWS)
    stage    = r.choice(_STAGES[workflow])
    source   = r.choice(_SOURCES)
    inc_type = r.choice(_INCIDENT_TYPES)
    severity = r.choices(_SEVERITIES, weights=_SEVERITY_WEIGHTS, k=1)[0]
    message  = r.choice(_MESSAGES[inc_type])
    category = r.choice(_CATEGORIES[inc_type])

    incident = StandardIncident(
        id=f"inc_{uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        workflow=workflow,
        stage=stage,
        source=source,
        incidentType=inc_type,  # type: ignore[arg-type]
        category=category,
        severity=severity,      # type: ignore[arg-type]
        message=message,
    )

    return EvaluationRequest(incident=incident)
