from __future__ import annotations

from fastapi import FastAPI

from .engine import evaluate
from .models import EvaluationRequest, EvaluationResult

app = FastAPI(title="LLM-QA-OPS Evaluation Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/evaluate", response_model=EvaluationResult)
def evaluate_endpoint(req: EvaluationRequest) -> EvaluationResult:
    return evaluate(req)