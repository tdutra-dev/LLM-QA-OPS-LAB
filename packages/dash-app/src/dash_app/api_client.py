"""
API client for the LLM-QA-OPS FastAPI evaluation service.

Provides Python functions to fetch data from all FastAPI endpoints for
dashboard visualization. Handles connection errors gracefully and returns
empty/default data when the backend is unavailable.

Configuration
─────────────
Set EVAL_API_URL environment variable to override the default FastAPI URL.
Default: http://localhost:8010
"""
from __future__ import annotations

import os
from typing import Any

import requests

# Configuration
EVAL_API_URL = os.getenv("EVAL_API_URL", "http://localhost:8010")
REQUEST_TIMEOUT = 5.0  # seconds


def get_health() -> dict[str, str]:
    """Get system health status."""
    try:
        response = requests.get(f"{EVAL_API_URL}/health", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"status": "error", "redis": "unknown"}


def get_metrics() -> dict[str, Any]:
    """Get aggregated metrics summary."""
    try:
        response = requests.get(f"{EVAL_API_URL}/metrics", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {
            "totalEvaluations": 0,
            "byStatus": [],
            "averageScore": 0.0,
            "bySeverity": {},
            "topSuggestedActions": [],
            "workflows": [],
        }


def get_analytics() -> dict[str, Any]:
    """Get rich analytics report (Pandas + Polars computed)."""
    try:
        response = requests.get(f"{EVAL_API_URL}/analytics", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {
            "totalRows": 0,
            "computedBy": "offline",
            "dailyScoreTrend": [],
            "rollingAvgScore": [],
            "severityDistrib": [],
            "workflowFailure": [],
        }


def get_incidents(workflow: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Get incident records with optional filtering."""
    try:
        params = {"limit": limit}
        if workflow:
            params["workflow"] = workflow
        if status:
            params["status"] = status
        
        response = requests.get(f"{EVAL_API_URL}/incidents", params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def get_actions(workflow: str | None = None, action_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Get action logs with optional filtering."""
    try:
        params = {"limit": limit}
        if workflow:
            params["workflow"] = workflow
        if action_type:
            params["action_type"] = action_type
            
        response = requests.get(f"{EVAL_API_URL}/actions", params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def get_agent_status() -> dict[str, Any]:
    """Get autonomous agent loop status."""
    try:
        response = requests.get(f"{EVAL_API_URL}/agent/status", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {
            "running": False,
            "cyclesCompleted": 0,
            "actionsExecuted": 0,
            "startedAt": None,
            "lastCycleAt": None,
            "intervalSeconds": None,
        }


def start_agent(interval: float = 5.0) -> dict[str, Any]:
    """Start the autonomous agent loop."""
    try:
        response = requests.post(
            f"{EVAL_API_URL}/agent/start", 
            params={"interval": interval}, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def stop_agent() -> dict[str, Any]:
    """Stop the autonomous agent loop."""
    try:
        response = requests.post(f"{EVAL_API_URL}/agent/stop", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}