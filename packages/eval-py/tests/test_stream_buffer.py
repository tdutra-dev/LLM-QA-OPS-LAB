"""
test_stream_buffer.py — Test suite per il Redis Stream buffer (Fase 3).

Cosa testiamo:
- push_to_stream(): XADD con i campi corretti, ritorna message ID
- drain_stream(): XRANGE nella finestra temporale, decode JSON corretto
- stream_length(): XLEN
- Graceful degradation: Redis non disponibile → None/lista vuota/0
- JSON malformato nello stream → ignorato senza eccezione
- _reset_for_testing(): permette di iniettare mock client tra test

Tutti i test mockano Redis — nessuna dipendenza esterna.
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import eval_py.stream_buffer as sb
from eval_py.stream_buffer import (
    STREAM_KEY,
    drain_stream,
    is_available,
    push_to_stream,
    stream_length,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """
    Resetta il singleton Redis prima di ogni test.
    Garantisce che ogni test parta da uno stato pulito,
    indipendente dall'ordine di esecuzione.
    """
    sb._reset_for_testing()
    yield
    sb._reset_for_testing()


@pytest.fixture
def mock_redis():
    """Mock redis client iniettato nel modulo."""
    client = MagicMock()
    client.ping.return_value = True
    with patch("eval_py.stream_buffer._get_client", return_value=client):
        yield client


@pytest.fixture
def redis_unavailable():
    """Simula Redis non raggiungibile."""
    with patch(
        "eval_py.stream_buffer._get_client",
        side_effect=Exception("Connection refused"),
    ):
        yield


# ── Test: is_available ────────────────────────────────────────────────────────

class TestIsAvailable:

    def test_returns_true_when_redis_responds(self, mock_redis):
        mock_redis.ping.return_value = True
        assert is_available() is True

    def test_returns_false_when_redis_unavailable(self, redis_unavailable):
        assert is_available() is False

    def test_returns_false_when_ping_raises(self, mock_redis):
        mock_redis.ping.side_effect = Exception("timeout")
        # _initialized è già True dopo _init(), ma ping lancia
        sb._initialized = True
        sb._redis = mock_redis
        assert is_available() is False


# ── Test: push_to_stream ──────────────────────────────────────────────────────

class TestPushToStream:

    def test_returns_message_id_on_success(self, mock_redis):
        mock_redis.xadd.return_value = "1712998800000-0"
        incident = {"service": "checkout-api", "severity": "high", "message": "error"}
        result = push_to_stream(incident)
        assert result == "1712998800000-0"

    def test_calls_xadd_with_correct_stream_key(self, mock_redis):
        mock_redis.xadd.return_value = "123-0"
        push_to_stream({"service": "payment-api", "message": "err"})
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == STREAM_KEY

    def test_serializes_incident_as_json_in_data_field(self, mock_redis):
        mock_redis.xadd.return_value = "123-0"
        incident = {"service": "checkout", "severity": "critical", "message": "NPE"}
        push_to_stream(incident)
        _, fields = mock_redis.xadd.call_args[0]
        assert "data" in fields
        decoded = json.loads(fields["data"])
        assert decoded["service"] == "checkout"
        assert decoded["severity"] == "critical"

    def test_applies_maxlen_to_prevent_unbounded_growth(self, mock_redis):
        mock_redis.xadd.return_value = "123-0"
        push_to_stream({"service": "x", "message": "y"})
        call_kwargs = mock_redis.xadd.call_args[1]
        assert "maxlen" in call_kwargs
        assert call_kwargs["maxlen"] == sb.MAX_LEN

    def test_returns_none_when_redis_unavailable(self, redis_unavailable):
        result = push_to_stream({"service": "x", "message": "y"})
        assert result is None

    def test_returns_none_when_xadd_raises(self, mock_redis):
        mock_redis.xadd.side_effect = Exception("XADD error")
        result = push_to_stream({"service": "x", "message": "y"})
        assert result is None

    def test_serializes_datetime_objects_via_default_str(self, mock_redis):
        """default=str in json.dumps deve gestire datetime senza eccezione."""
        mock_redis.xadd.return_value = "123-0"
        from datetime import datetime, timezone
        incident = {
            "service": "api",
            "timestamp": datetime(2026, 4, 13, 9, 0, 0, tzinfo=timezone.utc),
        }
        result = push_to_stream(incident)
        assert result == "123-0"


# ── Test: drain_stream ────────────────────────────────────────────────────────

class TestDrainStream:

    def _make_xrange_response(self, incidents: list[dict[str, Any]]) -> list:
        """Simula il formato che xrange restituisce con decode_responses=True."""
        return [
            (f"{i * 1000}-0", {"data": json.dumps(inc)})
            for i, inc in enumerate(incidents, start=1)
        ]

    def test_returns_empty_list_when_redis_unavailable(self, redis_unavailable):
        result = drain_stream(window_seconds=300)
        assert result == []

    def test_returns_list_of_decoded_incidents(self, mock_redis):
        incidents = [
            {"service": "checkout", "severity": "high"},
            {"service": "payment", "severity": "critical"},
        ]
        mock_redis.xrange.return_value = self._make_xrange_response(incidents)
        result = drain_stream(window_seconds=300)
        assert len(result) == 2
        assert result[0]["service"] == "checkout"
        assert result[1]["service"] == "payment"

    def test_calls_xrange_with_correct_stream_key(self, mock_redis):
        mock_redis.xrange.return_value = []
        drain_stream(window_seconds=300)
        call_args = mock_redis.xrange.call_args
        assert call_args[0][0] == STREAM_KEY

    def test_min_id_uses_window_seconds(self, mock_redis):
        """
        Verifica che min_id sia calcolato correttamente come (now - window) * 1000.
        Usiamo un'approssimazione di +/- 2 secondi per evitare flakiness.
        """
        mock_redis.xrange.return_value = []
        window = 300
        before = int((time.time() - window) * 1000)
        drain_stream(window_seconds=window)
        after = int((time.time() - window) * 1000)

        call_kwargs = mock_redis.xrange.call_args[1]
        min_id_str = call_kwargs["min"]
        min_ts_ms = int(min_id_str.split("-")[0])
        assert before - 2000 <= min_ts_ms <= after + 2000

    def test_returns_empty_list_when_no_events_in_window(self, mock_redis):
        mock_redis.xrange.return_value = []
        result = drain_stream(window_seconds=300)
        assert result == []

    def test_skips_messages_without_data_field(self, mock_redis):
        """Messaggi senza campo 'data' vengono ignorati silenziosamente."""
        mock_redis.xrange.return_value = [
            ("123-0", {}),                   # nessun campo data
            ("124-0", {"other": "field"}),   # campo diverso
            ("125-0", {"data": json.dumps({"service": "ok"})}),
        ]
        result = drain_stream(window_seconds=300)
        assert len(result) == 1
        assert result[0]["service"] == "ok"

    def test_skips_malformed_json_without_raising(self, mock_redis):
        """JSON malformato viene ignorato — non deve mai propagare un'eccezione."""
        mock_redis.xrange.return_value = [
            ("123-0", {"data": "not-valid-json"}),
            ("124-0", {"data": json.dumps({"service": "valid"})}),
        ]
        result = drain_stream(window_seconds=300)
        assert len(result) == 1
        assert result[0]["service"] == "valid"

    def test_returns_empty_list_when_xrange_raises(self, mock_redis):
        mock_redis.xrange.side_effect = Exception("XRANGE error")
        result = drain_stream(window_seconds=300)
        assert result == []


# ── Test: stream_length ───────────────────────────────────────────────────────

class TestStreamLength:

    def test_returns_xlen_value(self, mock_redis):
        mock_redis.xlen.return_value = 42
        assert stream_length() == 42

    def test_returns_zero_when_redis_unavailable(self, redis_unavailable):
        assert stream_length() == 0

    def test_returns_zero_when_xlen_raises(self, mock_redis):
        mock_redis.xlen.side_effect = Exception("XLEN error")
        sb._initialized = True
        sb._redis = mock_redis
        assert stream_length() == 0

    def test_stream_key_passed_to_xlen(self, mock_redis):
        mock_redis.xlen.return_value = 0
        stream_length()
        mock_redis.xlen.assert_called_once_with(STREAM_KEY)
