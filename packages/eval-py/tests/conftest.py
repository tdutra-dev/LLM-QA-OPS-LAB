"""
conftest.py — shared pytest fixtures for eval-py tests.
"""
from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def no_openai_key(monkeypatch):
    """
    Remove OPENAI_API_KEY for all tests by default.

    This ensures tests run without hitting real OpenAI APIs.
    Tests that require a real key should be marked with:
        @pytest.mark.integration
    and skipped in CI unless the secret is available.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
