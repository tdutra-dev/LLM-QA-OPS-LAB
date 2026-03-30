# LLM-QA-OPS-LAB

[![CI](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml/badge.svg)](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**Autonomous AI Agent for LLM Pipeline Monitoring & Remediation**

A production-grade distributed system that implements an autonomous AI agent capable of perceiving incidents, evaluating them via **OpenAI function calling**, retrieving historical context through **RAG with pgvector**, and orchestrating corrective actions — all observable via **Prometheus + Grafana** and deployed on **Kubernetes**.

Built as a cross-language monorepo (TypeScript + Python) following the same operational discipline as enterprise distributed systems.

## What This System Does

The agent runs a continuous loop:

1. **Perceives** incidents from a simulated runtime stream
2. **Evaluates** severity using OpenAI function calling (6 available tools)
3. **Retrieves** similar historical incidents via **RAG** (pgvector cosine similarity)
4. **Acts** autonomously — restart, scale, alert, escalate
5. **Exposes** every metric to Prometheus; visualized in a live Grafana dashboard

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        LLM-QA-OPS-LAB                                │
│                                                                      │
│  TypeScript Monorepo (pnpm workspaces)                               │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  @llmqa/   │  │  @llmqa/  │  │ @llmqa/  │  │  @llmqa/     │    │
│  │    core    │  │    llm    │  │   sim    │  │  contracts   │    │
│  │FeatureSpec │  │LLMAdapter │  │Simulator │  │ Shared types │    │
│  │ TestCase   │  │PromptEng  │  │FaultInj. │  │ TS + Python  │    │
│  └────────────┘  └────────────┘  └──────────┘  └──────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                                │
                      HTTP / shared contracts
                                │
┌──────────────────────────────────────────────────────────────────────┐
│                     Python Services                                  │
│                                                                      │
│  ┌─────────────────────────────────────────┐  ┌──────────────────┐  │
│  │          eval-py  (FastAPI :8010)        │  │  dash-app :8050  │  │
│  │                                          │  │                  │  │
│  │  POST /evaluate          (rule-based)    │  │  Real-time       │  │
│  │  POST /evaluate/tool-call (OpenAI FC)    │  │  monitoring      │  │
│  │  POST /evaluate/rag       (RAG + pgvec)  │  │  dashboard       │  │
│  │  GET  /prometheus-metrics (Prometheus)   │  │  Dash + Plotly   │  │
│  │  GET  /analytics          (Pandas/Polars)│  └──────────────────┘  │
│  │                                          │                        │
│  │  rag_retriever.py  ← pgvector <=> op     │                        │
│  │  rag_llamaindex.py ← LlamaIndex pipeline │                        │
│  │  metrics.py        ← 9 custom metrics    │                        │
│  │  agent_loop.py     ← autonomous loop     │                        │
│  │  action_executor.py← remediation actions │                        │
│  └──────────┬──────────────────┬────────────┘                        │
│             │                  │                                      │
│  ┌──────────▼──────┐  ┌────────▼───────┐                            │
│  │  PostgreSQL :5432│  │  Redis :6379   │                            │
│  │  + pgvector ext  │  │  Cache-aside   │                            │
│  │  VECTOR(1536)    │  │  TTL analytics │                            │
│  └─────────────────┘  └────────────────┘                            │
│                                                                      │
│  ┌──────────────────┐  ┌────────────────┐                           │
│  │  Prometheus :9090│  │  Grafana :3000 │                           │
│  │  SLO alerting    │  │  10-panel dash │                           │
│  └──────────────────┘  └────────────────┘                           │
└──────────────────────────────────────────────────────────────────────┘
                                │
                    Kubernetes (kind / minikube)
┌──────────────────────────────────────────────────────────────────────┐
│  Namespace: llmqa                                                    │
│  18 manifests · Kustomize · NetworkPolicy (least-privilege)          │
│  eval-py Deployment · dash-app Deployment · postgres StatefulSet     │
│  redis Deployment · nginx Ingress · GHCR image push on CI           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic V2 |
| **AI / LLM** | OpenAI GPT-4o-mini · Function Calling · Structured Outputs |
| **RAG** | pgvector (`<=>` cosine) · OpenAI `text-embedding-3-small` · LlamaIndex |
| **Frontend** | Dash · Plotly · Bootstrap 5 |
| **Analytics** | Pandas · Polars |
| **Database** | PostgreSQL 16 · pgvector extension · Redis 7 |
| **Observability** | Prometheus · Grafana · 9 custom metrics · SLO alerting rules |
| **Infrastructure** | Docker · Kubernetes · Kustomize · nginx Ingress |
| **CI/CD** | GitHub Actions · ruff · vitest · Trivy · GHCR image push |
| **TypeScript** | pnpm workspaces · Zod · Vitest · ESLint |

---

## Quick Start

### Local (Docker Compose)

```bash
git clone https://github.com/tdutra-dev/LLM-QA-OPS-LAB.git
cd LLM-QA-OPS-LAB

# Copy and fill your OpenAI key
cp .env.example .env

# Start full stack: API + Dashboard + PostgreSQL + Redis + Prometheus + Grafana
docker compose up --build -d

# Services
# FastAPI + Swagger:  http://localhost:8010/docs
# Dashboard:          http://localhost:8050
# Prometheus:         http://localhost:9090
# Grafana:            http://localhost:3000  (admin / llmqa_dev)
```

### Kubernetes

```bash
./scripts/k8s/build-images.sh
./scripts/k8s/deploy.sh

kubectl port-forward -n llmqa svc/eval-py-svc 8010:8010
kubectl port-forward -n llmqa svc/dash-app-svc 8050:8050
```

### Run Tests

```bash
# Python (19 unit tests, zero external deps)
cd packages/eval-py
pip install -e ".[dev]"
pytest tests/ -v

# TypeScript
pnpm test --run
```

---

## RAG Pipeline

Each incident evaluation auto-generates an OpenAI embedding (`text-embedding-3-small`, 1536 dims) stored directly in PostgreSQL via the `pgvector` extension.

**`POST /evaluate/rag`** retrieves the top-K most similar historical incidents using cosine distance, builds a context string, and uses it to enrich the evaluation:

```python
# Cosine similarity search in SQL
SELECT record_id, embedding <=> :query_embedding AS distance
FROM evaluation_records
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT :top_k
```

A higher-level **LlamaIndex pipeline** (`rag_llamaindex.py`) wraps the same pgvector store with `VectorStoreIndex` + `IngestionPipeline` + `QueryEngine` for GPT-4o-mini summarization of historical patterns.

Both layers degrade gracefully — if `OPENAI_API_KEY` is absent or pgvector is unavailable, the system falls back to standard evaluation without crashing.

---

## Observability

9 custom Prometheus metrics exposed at `GET /prometheus-metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `llmqa_eval_requests_total` | Counter | Requests by status (ok / needs_attention / critical) |
| `llmqa_eval_score` | Histogram | Score distribution (0–100) |
| `llmqa_rag_retrieval_latency_seconds` | Histogram | pgvector similarity search latency |
| `llmqa_rag_embedding_latency_seconds` | Histogram | OpenAI embedding generation latency |
| `llmqa_rag_similar_incidents_found` | Histogram | Number of similar incidents retrieved |
| `llmqa_rag_requests_total` | Counter | RAG requests by result (hit / miss) |
| `llmqa_agent_loop_iterations_total` | Counter | Agent loop cycles |
| `llmqa_agent_loop_errors_total` | Counter | Agent loop failures |
| `llmqa_action_executor_total` | Counter | Actions by type and outcome |

**SLO alerting rules** (`prometheus/alerts/slo.yml`):
- Availability: error rate < 1% per 5-minute window
- Latency: `/evaluate` p95 < 500ms · `/evaluate/rag` p95 < 300ms
- RAG hit rate > 60%
- Agent loop must execute at least once every 10 minutes

---

## CI/CD Pipeline

```
push / PR
    │
    ├── lint-py (ruff)      ─── eval-py + dash-app
    ├── test-py (pytest)    ─── 19 unit tests, offline
    ├── lint-ts (eslint)    ─── TypeScript packages
    ├── test-ts (vitest)    ─── TypeScript packages
    │
    └── [on green] ──► docker-build ──► GHCR push (main only)
                    └──► security-scan (Trivy → GitHub Security tab)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate` | Rule-based incident evaluation |
| `POST` | `/evaluate/tool-call` | AI-driven evaluation (OpenAI function calling) |
| `POST` | `/evaluate/rag` | RAG-enhanced evaluation with similar incidents |
| `GET` | `/health` | Service health |
| `GET` | `/metrics` | Real-time KPIs |
| `GET` | `/analytics` | Pandas/Polars aggregations |
| `GET` | `/actions` | Action execution history |
| `POST` | `/agent/start` | Start autonomous agent loop |
| `POST` | `/agent/stop` | Stop autonomous agent loop |
| `GET` | `/agent/status` | Agent activity metrics |
| `GET` | `/prometheus-metrics` | Prometheus scraping endpoint |

Interactive docs: `http://localhost:8010/docs`

---

## Implementation Roadmap (Completed)

| Step | Description | Key Technologies |
|------|-------------|-----------------|
| 1 | Monorepo architecture | pnpm workspaces, TypeScript, FeatureSpec domain |
| 2 | TestCase domain model | Fixtures, e-commerce checkout flow |
| 3 | LLM Adapter abstraction | Adapter pattern, MockLLMAdapter, provider-agnostic |
| 4 | Versioned Prompt Engine | Markdown templates, Zod schema validation |
| 5 | End-to-end test generation | FeatureSpec → LLM → TestCase[] pipeline |
| 6 | Production resilience layer | Retry/backoff, Timeout, Fallback, safe JSON parsing |
| 7 | KPI & Health Scoring | p50/p95/p99 latency, HEALTHY/DEGRADED/CRITICAL |
| 8 | Alert Engine + Incident Copilot | AlertEngine, OpenAI GPT-4o-mini reports |
| 9 | Runtime Simulator + Python service | FastAPI, Pydantic, cross-language contracts |
| 10 | Complete backend stack | PostgreSQL, Redis, Pandas, Polars, ActionExecutor |
| 11 | Kubernetes deployment | 18 manifests, Kustomize, multi-stage Dockerfile |
| 12 | RAG + Prometheus observability | pgvector, embeddings, 9 custom metrics, Grafana |
| 13 | LlamaIndex + CI/CD + Security | LlamaIndex, GitHub Actions, Trivy, NetworkPolicy, SLO alerts |

---

## About

Built by **[Tendresse Dutra](https://linkedin.com/in/tendresse-dutra)** — Backend & AI Systems Engineer.

Focus: distributed systems where LLM components are treated as operational services — observable, resilient, and autonomous.

