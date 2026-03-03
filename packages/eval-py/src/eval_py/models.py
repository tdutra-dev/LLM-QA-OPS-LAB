from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

Health = Literal["OK", "DEGRADED", "CRITICAL"]


class RunResult(BaseModel):
    ok: bool
    latencyMs: int = Field(ge=0)
    usedFallback: bool = False
    errorType: Optional[str] = None


class EvaluateRequest(BaseModel):
    windowId: str
    results: list[RunResult]


class KPIs(BaseModel):
    errorRate: float = Field(ge=0.0, le=1.0)
    avgLatency: float = Field(ge=0.0)
    fallbackRate: float = Field(ge=0.0, le=1.0)


class EvaluateResponse(BaseModel):
    health: Health
    kpis: KPIs
    reason: str