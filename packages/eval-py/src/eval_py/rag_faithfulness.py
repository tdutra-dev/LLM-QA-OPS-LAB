"""
rag_faithfulness.py — RAG Faithfulness Evaluator (Fase 4).

Misura se l'output del batch analyzer LLM è ancorato agli eventi reali
(grounding check) oppure contiene claim non supportati dai dati.

Due livelli:

1. Rule-based grounding checks (deterministico, sempre disponibile)
   - Tutti i services_affected nel result esistono davvero negli eventi?
   - I tipi di incident citati sono reali?
   - Il critical_pattern fa riferimento a entità reali?
   - Il severity assessment è coerente con la distribuzione reale?

2. LLM judge (opzionale, richiede OPENAI_API_KEY)
   - Un secondo LLM valuta indipendentemente la fedeltà dell'analisi
   - Structured output: faithfulness_score, ungrounded_claims, verdict
   - Se disponibile: score finale = (rule_score + llm_score) // 2

Perché questa metrica è importante per il CV:
  La domanda "come misuri RAG faithfulness senza ground truth?" è un classico
  delle interview AI Engineering. Questa implementazione mostra come si può
  fare: grounding check + LLM-as-judge = approccio industriale reale.

Metriche Prometheus:
  rag_faithfulness_score → Histogram → Grafana dashboard
  faithfulness_total → Counter per verdict (faithful/partially_faithful/hallucinated)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .models import BatchAnalysisResult, FaithfulnessResult, FaithfulnessRuleChecks

logger = logging.getLogger(__name__)

JUDGE_MODEL = "gpt-4o-mini"

_SEVERITY_RANK: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_CRITICAL_KEYWORDS: frozenset[str] = frozenset(
    {"critical", "urgent", "immediate", "severe", "emergency"}
)


# ── Event fact extraction ─────────────────────────────────────────────────────

def _extract_event_facts(
    events: list[dict[str, Any]],
) -> tuple[set[str], set[str], list[str]]:
    """
    Estrae i fatti di grounding dagli eventi raw.

    Returns:
        real_services       — set di service name effettivamente presenti
        real_incident_types — set di incident type effettivamente visti
        severities          — lista di severity per ogni evento
    """
    real_services: set[str] = set()
    real_incident_types: set[str] = set()
    severities: list[str] = []

    for ev in events:
        real_services.add(ev.get("service", "unknown"))
        inc_type = (
            ev.get("incident_type")
            or ev.get("incidentType")
            or "technical_error"
        )
        real_incident_types.add(inc_type)
        severities.append(ev.get("severity", "low"))

    return real_services, real_incident_types, severities


# ── Individual grounding checks ───────────────────────────────────────────────

def _check_services_grounding(
    services_affected: list[str],
    real_services: set[str],
) -> tuple[float, list[str]]:
    """
    Returns (grounded_ratio, ungrounded_services).

    grounded_ratio = 1.0 se services_affected è vuoto (vacuously true).
    """
    if not services_affected:
        return 1.0, []
    ungrounded = [s for s in services_affected if s not in real_services]
    grounded = len(services_affected) - len(ungrounded)
    ratio = grounded / len(services_affected)
    return ratio, ungrounded


def _check_incident_types_grounding(
    result: BatchAnalysisResult,
    real_incident_types: set[str],
) -> tuple[float, list[str]]:
    """
    Returns (grounded_ratio, ungrounded_types).

    Verifica i tipi di incident dichiarati in events_by_service.
    """
    claimed_types: set[str] = set()
    for svc in result.events_by_service:
        claimed_types.update(svc.incident_types)

    if not claimed_types:
        return 1.0, []

    ungrounded = [t for t in claimed_types if t not in real_incident_types]
    grounded = len(claimed_types) - len(ungrounded)
    ratio = grounded / len(claimed_types)
    return ratio, ungrounded


def _check_critical_pattern_grounding(
    critical_pattern: str | None,
    real_services: set[str],
    real_incident_types: set[str],
) -> bool:
    """
    Returns True se critical_pattern fa riferimento ad almeno un'entità reale
    (service name o incident type), o se critical_pattern è None.
    """
    if critical_pattern is None:
        return True
    pattern_lower = critical_pattern.lower()
    for entity in real_services | real_incident_types:
        if entity.lower() in pattern_lower:
            return True
    return False


def _check_severity_consistency(
    overall_assessment: str,
    severities: list[str],
) -> bool:
    """
    Returns True se il linguaggio di overall_assessment è coerente con la
    distribuzione reale delle severity negli eventi.

    Regola:
    - >= 50% eventi critical/high → l'assessment DEVE citare urgenza
    - < 20% eventi critical/high → l'assessment NON DEVE citare urgenza
    - 20-49% → True (range ambiguo, benefit of doubt)
    """
    if not severities:
        return True

    critical_high = sum(1 for s in severities if s in ("critical", "high"))
    ratio = critical_high / len(severities)
    assessment_text = overall_assessment.lower()
    mentions_urgent = any(kw in assessment_text for kw in _CRITICAL_KEYWORDS)

    if ratio >= 0.5 and not mentions_urgent:
        return False   # underreporting severity
    if ratio < 0.2 and mentions_urgent:
        return False   # overreporting severity
    return True


# ── Score & verdict ───────────────────────────────────────────────────────────

def _compute_rule_score(rule_checks: FaithfulnessRuleChecks) -> int:
    """
    Score composito 0-100 dai rule-based checks.

    Pesi:
      services_grounded_ratio              → 40 punti
      incident_types_grounded_ratio        → 30 punti
      critical_pattern_references_real...  → 10 punti
      severity_assessment_consistent       → 20 punti
    """
    score = (
        rule_checks.services_grounded_ratio * 40
        + rule_checks.incident_types_grounded_ratio * 30
        + (10 if rule_checks.critical_pattern_references_real_entity else 0)
        + (20 if rule_checks.severity_assessment_consistent else 0)
    )
    return int(score)


def _verdict(score: int) -> str:
    """
    Trasforma score numerico in verdetto categorico.

    >= 80 → faithful
    40–79 → partially_faithful
    < 40  → hallucinated
    """
    if score >= 80:
        return "faithful"
    if score >= 40:
        return "partially_faithful"
    return "hallucinated"


# ── LLM judge ─────────────────────────────────────────────────────────────────

_JUDGE_SYSTEM_PROMPT = """\
You are a RAG faithfulness evaluator. Your job is to assess whether a batch
analysis report is grounded in the actual events it was based on.

Rate faithfulness on these criteria:
1. Are the 'services_affected' all actually present in the events?
2. Are the 'incident_types' mentioned actually seen in the events?
3. Is the 'critical_pattern' (if any) supported by the event data?
4. Is the 'overall_assessment' severity consistent with the actual event severities?

Respond with valid JSON matching EXACTLY this schema:
{
  "faithfulness_score": <integer 0-100>,
  "ungrounded_claims": ["<claim1>", "<claim2>"],
  "verdict": "<faithful|partially_faithful|hallucinated>"
}

faithfulness_score: 0=completely hallucinated, 100=fully grounded in the data.
ungrounded_claims: list of specific claims in the analysis NOT supported by the events.
                   Empty list [] if all claims are grounded.
verdict: faithful (>=80), partially_faithful (40-79), hallucinated (<40)."""


def _call_llm_judge(
    result: BatchAnalysisResult,
    events: list[dict[str, Any]],
) -> tuple[int, list[str], str] | None:
    """
    Chiama OpenAI gpt-4o-mini come faithfulness judge.

    Returns (faithfulness_score, ungrounded_claims, verdict) o None se fallisce.

    OpenAI è importato dentro la funzione (stesso pattern di batch_analyzer)
    per evitare ImportError a module level se openai non è installato.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    # Costruisce contesto: max 50 eventi per non saturare il token budget
    event_lines = []
    for i, ev in enumerate(events[:50], 1):
        event_lines.append(
            f"{i}. service={ev.get('service', '?')} "
            f"severity={ev.get('severity', '?')} "
            f"type={ev.get('incident_type') or ev.get('incidentType', '?')} "
            f"msg={str(ev.get('message', ''))[:80]}"
        )

    user_prompt = (
        "BATCH ANALYSIS REPORT:\n"
        f"services_affected: {result.services_affected}\n"
        f"overall_assessment: {result.overall_assessment}\n"
        f"critical_pattern: {result.critical_pattern}\n"
        f"events_by_service: {[{'service': s.service, 'count': s.count, 'dominant_severity': s.dominant_severity, 'incident_types': s.incident_types} for s in result.events_by_service]}\n\n"
        f"ACTUAL EVENTS ({len(events)} total, showing first {min(50, len(events))}):\n"
        + "\n".join(event_lines)
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
            temperature=0.0,
        )

        raw = response.choices[0].message.content or "{}"
        parsed: dict[str, Any] = json.loads(raw)

        score = int(parsed.get("faithfulness_score", 50))
        score = max(0, min(100, score))
        claims = parsed.get("ungrounded_claims", [])
        if not isinstance(claims, list):
            claims = []
        verdict = parsed.get("verdict", "partially_faithful")
        if verdict not in ("faithful", "partially_faithful", "hallucinated"):
            verdict = _verdict(score)

        logger.info(
            "[faithfulness] LLM judge: score=%d verdict=%s ungrounded=%d",
            score,
            verdict,
            len(claims),
        )
        return score, claims, verdict

    except Exception as exc:
        logger.warning(
            "[faithfulness] LLM judge failed: %s — using rule-based only", exc
        )
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_faithfulness(
    result: BatchAnalysisResult,
    events: list[dict[str, Any]],
) -> FaithfulnessResult:
    """
    Valuta la fedeltà del batch analysis result rispetto agli eventi reali.

    Pipeline:
      1. Estrae i fatti reali dagli eventi (services, types, severities)
      2. Esegue rule-based grounding checks (deterministico)
      3. Calcola score rule-based (0-100) e verdict
      4. Se OPENAI_API_KEY disponibile: chiama LLM judge per score raffinato
         - Final score = (rule_score + llm_score) // 2
         - ungrounded_claims dal LLM sono più specifiche di quelle rule-based
      5. Ritorna FaithfulnessResult con tutte le informazioni

    Graceful degradation: se OpenAI non è disponibile, usa solo rule-based.
    Non solleva mai eccezioni al chiamante.
    """
    real_services, real_incident_types, severities = _extract_event_facts(events)

    # ── Rule-based checks ──────────────────────────────────────────────────
    services_ratio, ungrounded_services = _check_services_grounding(
        result.services_affected, real_services
    )
    types_ratio, ungrounded_types = _check_incident_types_grounding(
        result, real_incident_types
    )
    critical_pattern_grounded = _check_critical_pattern_grounding(
        result.critical_pattern, real_services, real_incident_types
    )
    severity_consistent = _check_severity_consistency(
        result.overall_assessment, severities
    )

    rule_checks = FaithfulnessRuleChecks(
        services_grounded_ratio=round(services_ratio, 3),
        incident_types_grounded_ratio=round(types_ratio, 3),
        critical_pattern_references_real_entity=critical_pattern_grounded,
        severity_assessment_consistent=severity_consistent,
    )

    rule_score = _compute_rule_score(rule_checks)

    # ── Build rule-based ungrounded claims ─────────────────────────────────
    ungrounded_claims: list[str] = []
    for svc in ungrounded_services:
        ungrounded_claims.append(
            f"Service '{svc}' mentioned but not found in events"
        )
    for typ in ungrounded_types:
        ungrounded_claims.append(
            f"Incident type '{typ}' mentioned but not observed in events"
        )
    if not critical_pattern_grounded:
        ungrounded_claims.append(
            "critical_pattern references entities not found in events"
        )
    if not severity_consistent:
        ungrounded_claims.append(
            "overall_assessment severity inconsistent with actual event distribution"
        )

    # ── Optional LLM judge ─────────────────────────────────────────────────
    llm_used = False
    llm_result = _call_llm_judge(result, events)

    if llm_result is not None:
        llm_score, llm_claims, _ = llm_result
        final_score = (rule_score + llm_score) // 2
        # Use LLM claims if non-empty (más específicas)
        final_claims = llm_claims if llm_claims else ungrounded_claims
        llm_used = True
    else:
        final_score = rule_score
        final_claims = ungrounded_claims

    final_verdict = _verdict(final_score)

    logger.info(
        "[faithfulness] batch_id=%s score=%d verdict=%s llm_used=%s",
        result.batch_id,
        final_score,
        final_verdict,
        llm_used,
    )

    return FaithfulnessResult(
        batch_id=result.batch_id,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        faithfulness_score=final_score,
        verdict=final_verdict,  # type: ignore[arg-type]
        rule_checks=rule_checks,
        ungrounded_claims=final_claims,
        llm_used=llm_used,
    )
