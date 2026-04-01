#!/usr/bin/env python3
"""
LLM-QA-OPS Load Generator — Grafana Showcase
─────────────────────────────────────────────
Sends realistic traffic to the eval-py service to populate Grafana dashboards
with evaluation metrics, RAG metrics, HTTP latency histograms, and more.

Usage:
    python scripts/load_generator.py [--url URL] [--duration SECONDS] [--rps N]

Examples:
    python scripts/load_generator.py                        # default: port 8011, 120s
    python scripts/load_generator.py --url http://localhost:8010 --duration 300
"""

import argparse
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ─── Realistic incident data ────────────────────────────────────────────────

WORKFLOWS = [
    "checkout-flow", "support-triage", "document-qa",
    "code-review", "fraud-detection", "content-moderation",
    "customer-onboarding", "lead-scoring",
]

STAGES = [
    "retrieval", "generation", "validation", "ranking",
    "embedding", "reranking", "postprocessing",
]

INCIDENT_TYPES = [
    "technical_error", "schema_error", "semantic_error", "degradation"
]

SEVERITIES = ["low", "medium", "high", "critical"]
SEVERITY_WEIGHTS = [0.4, 0.35, 0.18, 0.07]  # mostly low/medium, occasional high/critical

SOURCES = [
    "gpt-4o-mini", "gpt-4o", "claude-3-haiku", "llama-3.1-8b",
    "embed-ada-002", "bge-large-en", "mistral-7b",
]

MESSAGES = {
    "technical_error": [
        "OpenAI API timeout after 30s — retrying with fallback model",
        "Rate limit exceeded: 429 Too Many Requests from upstream LLM provider",
        "Vector DB connection pool exhausted — pgvector query failed",
        "Redis cache miss storm detected: 98% miss rate in last 60s",
        "Embedding service returned malformed response (NaN values)",
    ],
    "schema_error": [
        "LLM output failed JSON schema validation: missing required field 'reasoning'",
        "Response truncated at token limit — structured output incomplete",
        "Unexpected field 'confidence_score' not in expected schema v2.1",
        "Pydantic validation error: 'severity' must be one of [low, medium, high, critical]",
    ],
    "semantic_error": [
        "Hallucination detected: LLM cited non-existent knowledge base article KB-99999",
        "Answer contradicts retrieved context (cosine similarity: 0.12)",
        "Off-topic response: query about billing answered with product specs",
        "Low coherence score (0.31): response sections are semantically inconsistent",
    ],
    "degradation": [
        "p95 latency degraded: 2.8s vs SLO target of 500ms",
        "Retrieval quality drop: average relevance score fell below threshold (0.45 < 0.65)",
        "Token efficiency degraded: average 4200 tokens/request vs baseline 1800",
        "RAG hit rate degraded from 0.89 to 0.61 in the last 15 minutes",
    ],
}

CATEGORIES = [
    "llm-timeout", "schema-validation", "retrieval-quality", "hallucination",
    "rate-limiting", "cache-performance", "latency-slo", "token-budget",
]


def random_incident() -> dict:
    incident_type = random.choice(INCIDENT_TYPES)
    severity = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
    return {
        "id": f"INC-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow": random.choice(WORKFLOWS),
        "stage": random.choice(STAGES),
        "incidentType": incident_type,
        "category": random.choice(CATEGORIES),
        "severity": severity,
        "source": random.choice(SOURCES),
        "message": random.choice(MESSAGES[incident_type]),
        "context": {
            "latency_ms": round(random.uniform(50, 3500), 1),
            "tokens_used": random.randint(200, 8000),
            "model_version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}",
            "rag_hits": random.randint(0, 5),
            "score": round(random.uniform(0.1, 0.99), 3),
        },
    }


def send_evaluate(base_url: str, endpoint: str = "/evaluate") -> dict:
    payload = {"incident": random_incident()}
    url = f"{base_url}{endpoint}"
    t0 = time.perf_counter()
    resp = requests.post(url, json=payload, timeout=30)
    latency = (time.perf_counter() - t0) * 1000
    return {"url": url, "status": resp.status_code, "latency_ms": latency}


def send_get(base_url: str, path: str) -> dict:
    url = f"{base_url}{path}"
    t0 = time.perf_counter()
    resp = requests.get(url, timeout=10)
    latency = (time.perf_counter() - t0) * 1000
    return {"url": url, "status": resp.status_code, "latency_ms": latency}


def run_load(base_url: str, duration_sec: float, target_rps: float) -> None:
    print(f"\n🚀  LLM-QA-OPS Load Generator")
    print(f"   Target : {base_url}")
    print(f"   Duration: {duration_sec}s  |  RPS: {target_rps}")
    print(f"   Start  : {datetime.now().strftime('%H:%M:%S')}\n")

    start = time.time()
    interval = 1.0 / target_rps
    total = success = errors = 0
    latencies: list[float] = []

    # Endpoint weights: heavy on /evaluate and /evaluate/rag, lighter on GET routes
    endpoints = [
        ("/evaluate",            0.45),
        ("/evaluate/rag",        0.35),
        ("/evaluate/tool-call",  0.05),
        ("/health",              0.05),
        ("/analytics",           0.04),
        ("/incidents",           0.03),
        ("/agent/status",        0.03),
    ]
    paths, weights = zip(*endpoints)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []

        while time.time() - start < duration_sec:
            path = random.choices(paths, weights=weights)[0]

            if path.startswith("/evaluate"):
                fut = pool.submit(send_evaluate, base_url, path)
            else:
                fut = pool.submit(send_get, base_url, path)

            futures.append(fut)
            time.sleep(interval + random.uniform(-interval * 0.2, interval * 0.2))

            # Drain completed futures periodically
            if len(futures) >= 20:
                done = [f for f in futures if f.done()]
                for f in done:
                    futures.remove(f)
                    try:
                        res = f.result()
                        total += 1
                        latencies.append(res["latency_ms"])
                        if 200 <= res["status"] < 300:
                            success += 1
                        else:
                            errors += 1
                    except Exception as exc:
                        errors += 1
                        print(f"  ⚠  {exc}")

            elapsed = time.time() - start
            if total > 0 and total % 20 == 0:
                p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
                print(
                    f"  [{elapsed:5.0f}s]  requests={total:4d}  "
                    f"ok={success}  err={errors}  "
                    f"p50={p50:.0f}ms"
                )

        # Wait for remaining futures
        for f in as_completed(futures, timeout=30):
            try:
                res = f.result()
                total += 1
                latencies.append(res["latency_ms"])
                if 200 <= res["status"] < 300:
                    success += 1
            except Exception:
                errors += 1

    elapsed = time.time() - start
    if latencies:
        s = sorted(latencies)
        p50 = s[len(s) // 2]
        p95 = s[int(len(s) * 0.95)]
        p99 = s[int(len(s) * 0.99)]
    else:
        p50 = p95 = p99 = 0

    print(f"\n✅  Done in {elapsed:.1f}s")
    print(f"   Total requests : {total}")
    print(f"   Success (2xx)  : {success}")
    print(f"   Errors         : {errors}")
    print(f"   Throughput     : {total/elapsed:.1f} req/s")
    print(f"   Latency p50/p95/p99 : {p50:.0f}/{p95:.0f}/{p99:.0f} ms")
    print(f"\n   → Open Grafana: http://localhost:3000")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-QA-OPS Grafana load generator")
    parser.add_argument("--url", default="http://localhost:8011", help="Base URL of eval-py")
    parser.add_argument("--duration", type=float, default=180, help="Duration in seconds (default: 180)")
    parser.add_argument("--rps", type=float, default=3.0, help="Requests per second (default: 3)")
    args = parser.parse_args()

    # Sanity check: is the service up?
    try:
        r = requests.get(f"{args.url}/health", timeout=5)
        r.raise_for_status()
        print(f"✓  Service health: {r.json()}")
    except Exception as exc:
        print(f"✗  Cannot reach {args.url}/health → {exc}")
        raise SystemExit(1)

    run_load(base_url=args.url, duration_sec=args.duration, target_rps=args.rps)


if __name__ == "__main__":
    main()
