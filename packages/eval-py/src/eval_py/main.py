from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .engine import evaluate
from .models import EvaluateRequest, EvaluateResponse

app = FastAPI(title="LLM-QA-OPS eval-py", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    version: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate_endpoint(req: EvaluateRequest) -> EvaluateResponse:
    return evaluate(req)