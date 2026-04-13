"""
stream_buffer.py — Redis Stream buffer per gli incident in ingestion.

Il problema che risolve:
  Gli endpoint /ingest/* elaborano un evento alla volta.
  Il batch analyzer ha bisogno di vedere TUTTI gli eventi di una finestra temporale
  in una volta sola — per identificare pattern cross-service che un'analisi
  evento-per-evento non può vedere.

  Questo modulo è il buffer: ogni evento normalizzato viene scritto nello stream,
  il batch analyzer drena la finestra quando vuole fare l'analisi.

Redis Stream vs alternative:
  • List  → LPUSH/RPOP: nessun time-range nativo, difficile fare finestre temporali
  • Pub/Sub → fire-and-forget: se il batch analyzer è down, perde i messaggi
  • Stream → XADD/XRANGE: ID basati su timestamp, finestra temporale triviale,
             at-least-once delivery, MAXLEN per controllare la dimensione

Come funziona il time-windowing:
  Gli ID dei messaggi Redis Stream sono "<timestamp_ms>-<seq>".
  Per XRANGE degli ultimi N secondi basta specificare come minimo:
      min_id = f"{int((now - window_seconds) * 1000)}-0"
  Nessun campo extra, nessuna query: il timestamp è già nell'ID.

Graceful degradation:
  Se Redis non è disponibile, push_to_stream() ritorna None e drain_stream()
  ritorna lista vuota. I test dell'endpoint passano comunque, il batch analyzer
  riceve 0 eventi e usa il fallback rule-based.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import redis

logger = logging.getLogger(__name__)

STREAM_KEY = "stream:incidents"
MAX_LEN = 10_000   # MAXLEN ~ — approx trim, previene stream unbounded

# ── Lazy singleton ────────────────────────────────────────────────────────────

_redis: redis.Redis | None = None
_initialized: bool = False


def _get_client() -> redis.Redis:
    """
    Crea un client Redis dal REDIS_URL env var.

    decode_responses=True: XRANGE restituisce stringhe, non bytes.
    Questo semplifica il parsing JSON del campo "data".
    """
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _init() -> None:
    """Connect once; cache result in module-level singleton."""
    global _redis, _initialized
    if _initialized:
        return
    _initialized = True
    try:
        client = _get_client()
        client.ping()
        _redis = client
        logger.info("[stream] Redis Stream connected")
    except Exception as exc:
        logger.warning("[stream] Redis unavailable (%s) — stream buffer disabled", exc)
        _redis = None


def _reset_for_testing() -> None:
    """Reset singleton state. Used by tests to inject a mock client."""
    global _redis, _initialized
    _redis = None
    _initialized = False


# ── Public API ─────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True se Redis Stream è raggiungibile."""
    _init()
    if _redis is None:
        return False
    try:
        return bool(_redis.ping())
    except Exception:
        return False


def push_to_stream(incident_data: dict[str, Any]) -> str | None:
    """
    XADD un incident normalizzato allo stream.

    Perché serializziamo tutto in un campo "data":
      Redis Stream richiede campi di tipo string. Serializzare l'intero dict
      come JSON in "data" è più semplice e flessibile che mappare ogni campo
      a un campo separato — e rende drain_stream agnostico alla struttura.

    Returns:
      Il message ID (e.g. "1712998800000-0") in formato stringa, o None se
      Redis non è disponibile o XADD fallisce.
    """
    _init()
    if _redis is None:
        return None
    try:
        msg_id = _redis.xadd(
            STREAM_KEY,
            {"data": json.dumps(incident_data, default=str)},
            maxlen=MAX_LEN,
            approximate=True,
        )
        logger.debug("[stream] XADD id=%s service=%s", msg_id, incident_data.get("service"))
        return str(msg_id) if msg_id else None
    except Exception as exc:
        logger.warning("[stream] XADD failed: %s", exc)
        return None


def drain_stream(window_seconds: int = 300) -> list[dict[str, Any]]:
    """
    XRANGE: tutti gli eventi degli ultimi window_seconds.

    Strategia:
      min_id = "<(now_ms - window_ms)>-0"  → seleziona dalla finestra temporale
      max   = "+"                           → fino all'ultimo messaggio

    Returns:
      Lista di dict con i campi dell'incident normalizzato.
      Lista vuota se Redis non disponibile, errore, o nessun evento nella finestra.
    """
    _init()
    if _redis is None:
        return []
    try:
        min_ts_ms = int((time.time() - window_seconds) * 1000)
        min_id = f"{min_ts_ms}-0"
        messages = _redis.xrange(STREAM_KEY, min=min_id, max="+")
        result: list[dict[str, Any]] = []
        for _msg_id, fields in messages:
            raw = fields.get("data")
            if raw:
                try:
                    result.append(json.loads(raw))
                except json.JSONDecodeError as exc:
                    logger.warning("[stream] JSON decode error in XRANGE: %s", exc)
        logger.debug("[stream] drained %d events (window=%ds)", len(result), window_seconds)
        return result
    except Exception as exc:
        logger.warning("[stream] XRANGE failed: %s", exc)
        return []


def stream_length() -> int:
    """XLEN — numero di messaggi attualmente nello stream."""
    _init()
    if _redis is None:
        return 0
    try:
        return int(_redis.xlen(STREAM_KEY))
    except Exception:
        return 0
