from __future__ import annotations

from .models import EvaluationRequest, EvaluationResult


def evaluate(req: EvaluationRequest) -> EvaluationResult:
    incident = req.incident

    incident_type = incident.incidentType
    severity = incident.severity
    category = incident.category

    # Schema errors usually block downstream structured processing.
    if incident_type == "schema_error":
        return EvaluationResult(
            status="critical",
            score=85 if severity in ("high", "critical") else 70,
            summary="Schema validation failure detected in the workflow.",
            reasoning=(
                "The incident was classified as a schema error, which means the "
                "LLM output could not be safely consumed by downstream components."
            ),
            suggestedAction="inspect_schema",
            tags=["schema_error", category, incident.stage],
        )

    # Technical errors may depend on provider/network/runtime issues.
    if incident_type == "technical_error":
        if severity in ("high", "critical"):
            return EvaluationResult(
                status="critical",
                score=80,
                summary="Critical technical failure detected in the workflow.",
                reasoning=(
                    "A high-severity technical error suggests that the workflow "
                    "was interrupted by infrastructure, provider, or runtime issues."
                ),
                suggestedAction="check_provider",
                tags=["technical_error", category, incident.source],
            )

        return EvaluationResult(
            status="needs_attention",
            score=60,
            summary="Technical issue detected in the workflow.",
            reasoning=(
                "The incident was classified as a technical error, but its current "
                "severity does not indicate a full critical failure."
            ),
            suggestedAction="monitor",
            tags=["technical_error", category, incident.source],
        )

    # Semantic errors are valid outputs with low usefulness/correctness.
    if incident_type == "semantic_error":
        return EvaluationResult(
            status="needs_attention",
            score=65 if severity in ("high", "critical") else 50,
            summary="Semantic quality issue detected in the workflow output.",
            reasoning=(
                "The model produced an output that is structurally valid but may be "
                "incorrect, misleading, or not useful for the intended task."
            ),
            suggestedAction="inspect_prompt",
            tags=["semantic_error", category, incident.workflow],
        )

    # Degradation means the workflow is not broken but is getting worse.
    if incident_type == "degradation":
        return EvaluationResult(
            status="needs_attention",
            score=55 if severity in ("low", "medium") else 70,
            summary="Workflow degradation detected.",
            reasoning=(
                "The workflow is still operating, but signals indicate worsening "
                "performance or reliability over time."
            ),
            suggestedAction="monitor",
            tags=["degradation", category, incident.workflow],
        )

    # Defensive fallback, should rarely happen because models use constrained literals.
    return EvaluationResult(
        status="needs_attention",
        score=50,
        summary="Unclassified incident received by evaluation service.",
        reasoning=(
            "The evaluation service received an incident that could not be matched "
            "to a specialized evaluation rule."
        ),
        suggestedAction="escalate",
        tags=["unclassified"],
    )