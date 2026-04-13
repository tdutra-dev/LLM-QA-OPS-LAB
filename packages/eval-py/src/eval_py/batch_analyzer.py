"""
batch_analyzer.py — Analisi batch LLM su una finestra di incident.

Il cuore della Fase 3 e il primo strato del LLM Evaluation Framework.

Perché batch e non evento-per-evento:
  Un LLM che legge 1 evento alla volta è cieco ai pattern:
    - "Il checkout-api ha avuto 12 timeout in 5 minuti"
    - "Contemporaneamente il payment-service ha avuto 8 errori di schema"
  → Il LLM event-by-event vede 20 eventi separati.
  → Il LLM batch vede "C'è una cascata di errori tra checkout e payment".

  Questo è esattamente il valore aggiunto di LLM-QA-OPS-LAB rispetto a
  sistemi rule-based tradizionali.

Evaluation layer integrato:
  I campi `hallucination_risk` e `confidence_score` nel risultato sono la prima
  metrica di qualità LLM del sistema. Il LLM auto-valuta quanto è sicuro della
  propria analisi basandosi sui dati ricevuti:
    - hallucination_risk="low"    → analisi fortemente ancorata ai dati
    - hallucination_risk="medium" → inferenze ragionevoli oltre i dati
    - hallucination_risk="high"   → dati insufficienti, alta incertezza
  Questi vengono esposti come Prometheus metrics → visibili in Grafana.

Graceful degradation:
  Se OPENAI_API_KEY non è impostato, _build_fallback_result() produce un
  BatchAnalysisResult rule-based dall'aggregazione degli eventi.
  Con llm_used=False e confidence_score=40 per indicare analisi limitata.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .models import BatchAnalysisResult, BatchEventSummary

logger = logging.getLogger(__name__)

BATCH_MODEL = "gpt-4o-mini"

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert SRE (Site Reliability Engineer) analyzing a batch of normalized
operational incidents from a production system.

Your task is to identify patterns, correlations, and the overall health situation
across ALL events together — not each event in isolation.

You MUST respond with valid JSON matching EXACTLY this schema:
{
  "overall_assessment": "<string: 2-3 sentences describing the overall situation>",
  "critical_pattern": "<string or null: the most critical pattern identified, null if none>",
  "recommended_actions": ["<action1>", "<action2>"],
  "events_by_service": [
    {
      "service": "<string>",
      "count": <integer>,
      "dominant_severity": "<low|medium|high|critical>",
      "incident_types": ["<type1>", "<type2>"]
    }
  ],
  "hallucination_risk": "<low|medium|high>",
  "confidence_score": <integer 0-100>
}

hallucination_risk assessment criteria:
  "low"    — your assessment is directly supported by the event data provided
  "medium" — you are making reasonable inferences that go slightly beyond the raw data
  "high"   — you have very limited data, events are ambiguous, or you are speculating

confidence_score: your confidence in this analysis (0=no data/random, 100=very clear pattern).
"""


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_prompt(events: list[dict[str, Any]], window_seconds: int) -> str:
    """
    Costruisce il prompt utente per il batch analyzer.

    Ogni evento viene rappresentato su una riga con i campi più rilevanti.
    Il messaggio viene troncato a 120 caratteri per contenere il prompt.
    """
    n = len(events)
    window_min = window_seconds // 60
    lines = [
        f"You have received {n} incident event(s) in the last {window_min} minutes.",
        "Analyze the pattern and identify what is happening across all services.",
        "",
        "INCIDENTS:",
    ]
    for i, ev in enumerate(events, 1):
        service = ev.get("service", "unknown")
        severity = ev.get("severity", "unknown")
        source = ev.get("source_system", "unknown")
        incident_type = ev.get("incident_type") or ev.get("incidentType") or "unknown"
        message = str(ev.get("message", ""))[:120]
        lines.append(
            f"{i}. [{service}] severity={severity} type={incident_type} source={source} | {message}"
        )
    return "\n".join(lines)


# ── Fallback rule-based analysis ──────────────────────────────────────────────

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _build_fallback_result(
    events: list[dict[str, Any]], window_seconds: int
) -> BatchAnalysisResult:
    """
    Analisi rule-based quando OpenAI non è disponibile.

    Aggrega gli eventi per service, identifica il severity dominante,
    e produce un assessment basato su soglie semplici.

    confidence_score=40: meno del LLM perché non vede correlazioni.
    hallucination_risk="low": nessun LLM → nessuna allucinazione.
    """
    if not events:
        return BatchAnalysisResult(
            batch_id=f"batch_{uuid4().hex[:8]}",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            event_count=0,
            window_seconds=window_seconds,
            services_affected=[],
            overall_assessment="No events in the current window.",
            critical_pattern=None,
            recommended_actions=[],
            events_by_service=[],
            hallucination_risk="low",
            confidence_score=0,
            llm_used=False,
        )

    service_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        service_events[ev.get("service", "unknown")].append(ev)

    events_by_service: list[BatchEventSummary] = []
    for svc, evs in service_events.items():
        severities = [e.get("severity", "low") for e in evs]
        types_seen: list[str] = list(
            {e.get("incident_type") or e.get("incidentType") or "technical_error" for e in evs}
        )
        dominant = max(severities, key=lambda s: _SEVERITY_RANK.get(s, 0))
        events_by_service.append(
            BatchEventSummary(
                service=svc,
                count=len(evs),
                dominant_severity=dominant,  # type: ignore[arg-type]
                incident_types=types_seen,
            )
        )

    services_affected = list(service_events.keys())
    critical_count = sum(
        1 for ev in events if ev.get("severity") in ("critical", "high")
    )

    if critical_count > len(events) * 0.5:
        assessment = (
            f"High volume of critical/high severity incidents across "
            f"{len(services_affected)} service(s). "
            f"{critical_count} of {len(events)} events require immediate attention."
        )
        pattern: str | None = (
            f"Elevated error rate: {critical_count}/{len(events)} events are high/critical severity"
        )
        actions = [
            "Investigate affected services immediately",
            "Check infrastructure health",
            "Consider rollback if recent deployment",
        ]
    else:
        assessment = (
            f"Received {len(events)} incident event(s) across {len(services_affected)} "
            f"service(s) in the last {window_seconds // 60} minutes. "
            "No critical pattern detected by rule-based analysis."
        )
        pattern = None
        actions = ["Monitor situation", "Review individual incident logs"]

    return BatchAnalysisResult(
        batch_id=f"batch_{uuid4().hex[:8]}",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        event_count=len(events),
        window_seconds=window_seconds,
        services_affected=services_affected,
        overall_assessment=assessment,
        critical_pattern=pattern,
        recommended_actions=actions,
        events_by_service=events_by_service,
        hallucination_risk="low",
        confidence_score=40,
        llm_used=False,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def run_batch_analysis(
    events: list[dict[str, Any]],
    window_seconds: int = 300,
) -> BatchAnalysisResult:
    """
    Analizza un batch di incident con una singola chiamata OpenAI.

    Questo è il valore differenziale di Fase 3: il LLM vede TUTTI gli eventi
    della finestra temporale insieme, non uno alla volta.

    Flusso:
      1. Se non ci sono eventi → return empty result
      2. Se no OPENAI_API_KEY → fallback rule-based
      3. Costruisci prompt con tutti gli eventi
      4. Una sola chiamata OpenAI con response_format=json_object
      5. Parsa e valida il risultato strutturato
      6. Se parsing fallisce → fallback rule-based

    Il `hallucination_risk` nel risultato è la prima metrica di evaluation:
    il LLM auto-valuta quanto è certa la propria analisi → Prometheus metric.
    """
    if not events:
        return BatchAnalysisResult(
            batch_id=f"batch_{uuid4().hex[:8]}",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            event_count=0,
            window_seconds=window_seconds,
            services_affected=[],
            overall_assessment="No events in the current window.",
            critical_pattern=None,
            recommended_actions=[],
            events_by_service=[],
            hallucination_risk="low",
            confidence_score=0,
            llm_used=False,
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("[batch] OPENAI_API_KEY not set — using rule-based fallback")
        return _build_fallback_result(events, window_seconds)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        user_prompt = _build_user_prompt(events, window_seconds)

        response = client.chat.completions.create(
            model=BATCH_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
            temperature=0.1,  # bassa temperatura = analisi più deterministica
        )

        raw_json = response.choices[0].message.content or "{}"
        parsed: dict[str, Any] = json.loads(raw_json)

        # Costruisce events_by_service dal JSON del LLM, validando ogni entry
        events_by_service: list[BatchEventSummary] = []
        for svc_data in parsed.get("events_by_service", []):
            try:
                events_by_service.append(BatchEventSummary(**svc_data))
            except (ValidationError, TypeError) as exc:
                logger.warning("[batch] Skipping malformed events_by_service entry: %s", exc)

        # Deriva services_affected dall'aggregato — più affidabile del LLM che
        # potrebbe dimenticare qualche service nel JSON
        services_from_llm = [s.service for s in events_by_service]
        services_from_events = list({ev.get("service", "unknown") for ev in events})
        services_affected = services_from_llm or services_from_events

        hallucination_risk = parsed.get("hallucination_risk", "medium")
        if hallucination_risk not in ("low", "medium", "high"):
            hallucination_risk = "medium"

        confidence_score = int(parsed.get("confidence_score", 50))
        confidence_score = max(0, min(100, confidence_score))

        logger.info(
            "[batch] LLM analysis complete: %d events, hallucination_risk=%s, confidence=%d",
            len(events),
            hallucination_risk,
            confidence_score,
        )

        return BatchAnalysisResult(
            batch_id=f"batch_{uuid4().hex[:8]}",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            event_count=len(events),
            window_seconds=window_seconds,
            services_affected=services_affected,
            overall_assessment=parsed.get("overall_assessment", "Analysis unavailable."),
            critical_pattern=parsed.get("critical_pattern"),
            recommended_actions=parsed.get("recommended_actions", []),
            events_by_service=events_by_service,
            hallucination_risk=hallucination_risk,  # type: ignore[arg-type]
            confidence_score=confidence_score,
            llm_used=True,
            raw_llm_response=raw_json,
        )

    except Exception as exc:
        logger.warning(
            "[batch] OpenAI call failed: %s — falling back to rule-based", exc
        )
        return _build_fallback_result(events, window_seconds)
