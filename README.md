# LLM-QA-OPS-LAB

[![CI](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml/badge.svg)](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**AIOps Intelligence Layer — Universal Incident Analysis & Autonomous Remediation**

A production-grade distributed system evolving into a **universal AIOps intelligence layer**: any production system (Spring Boot, Kafka, Node.js, cloud services) sends incidents via HTTP or event streams, they are normalized into a common format, accumulated by time window, and analyzed in batch by an LLM — producing structured awareness, root cause classification, and remediation suggestions without calling the AI once per event.

Built as a cross-language monorepo (TypeScript + Python) following the same operational discipline as enterprise distributed systems.

---

## The Problem This Solves

In any company with multiple services in production:

- **500+ alerts per day** from different systems, each in a different format
- **Operators see noise**, not patterns — the real issue hides in the correlation
- **Calling an LLM per event** is slow, expensive, and context-blind
- **Existing tools** (PagerDuty, Splunk, BigPanda) are proprietary, expensive, and don't natively use LLMs for semantic root cause analysis

LLM-QA-OPS-LAB answers: *"given everything that happened in the last 5 minutes across all your services — what is actually wrong, and what should you do?"*

---

## What This System Does — Current State

The core evaluation engine runs a continuous loop:

1. **Receives** incident events — currently from an LLM pipeline (generalized ingestion layer in progress)
2. **Evaluates** severity using three strategies: rule-based, OpenAI function calling, RAG on historical incidents
3. **Retrieves** context from similar past incidents via **RAG** (pgvector cosine similarity, 4800+ embeddings in DB)
4. **Acts** autonomously via a **LangGraph StateGraph** — restart, scale, alert, escalate
5. **Exposes** every metric to Prometheus, visualized in a live Grafana dashboard with SLO alerting

---

## Target Architecture — Universal AIOps Intelligence Layer

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ANY SYSTEM IN PRODUCTION                          │
│  Java Spring Boot · Kafka · MySQL · Node.js · AWS · Python services  │
│              HTTP webhooks  or  event-driven streams                 │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                INGESTION LAYER  (in progress — Phase 2)              │
│   POST /ingest/http-log     ← Spring Boot, any app                  │
│   POST /ingest/kafka-event  ← Kafka consumer                        │
│   POST /ingest/webhook      ← GitHub, PagerDuty, Datadog, custom    │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│             NORMALIZATION LAYER  (in progress — Phase 1)             │
│   Every source format → IncidentEvent (universal typed model)        │
│   SpringBootNormalizer · KafkaNormalizer · WebhookNormalizer         │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│              ACCUMULATOR — Redis Streams  (Phase 3)                  │
│   Buffer by time window (e.g. 5 min) · group by service + severity  │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓  one batch call, not one call per event
┌──────────────────────────────────────────────────────────────────────┐
│              LLM ANALYSIS ENGINE  (built — being generalized)        │
│   Single OpenAI call with full 5-minute context window               │
│   → root cause classification · incident grouping · action proposal  │
│   RAG: pgvector similarity search on 4800+ historical incidents      │
│   LangGraph StateGraph: perceive→retrieve→evaluate→act→audit         │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                       OUTPUT LAYER                                   │
│   Structured incident report · Prometheus metrics · Grafana dashboard│
│   Slack / Jira / email  (action_executor.py)                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Current Architecture — Built & Running

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
│  │  langgraph_agent.py← LangGraph pipeline  │                        │
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
| **Agentic** | LangGraph `StateGraph` · typed state · `MemorySaver` checkpointing |
| **RAG** | pgvector (`<=>` cosine) · OpenAI `text-embedding-3-small` · LlamaIndex |
| **Ingestion** | HTTP webhooks · Kafka events · pluggable Normalizer pattern *(in progress)* |
| **Frontend** | Dash · Plotly · Bootstrap 5 |
| **Analytics** | Pandas · Polars |
| **Database** | PostgreSQL 16 · pgvector extension · Redis 7 · Redis Streams *(in progress)* |
| **Observability** | Prometheus · Grafana · 9 custom metrics · SLO alerting rules |
| **Infrastructure** | Docker · Kubernetes · Kustomize · nginx Ingress |
| **CI/CD** | GitHub Actions · ruff · pytest · vitest · Trivy · GHCR image push |
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

## Implementation Roadmap

### Completed — LLM Pipeline Quality Gate (Steps 1–14)

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
| 14 | LangGraph agentic pipeline | LangGraph StateGraph, TypedDict state, RAG-augmented evaluation, MemorySaver |

---

### In Progress — Universal AIOps Intelligence Layer (Phases 1–4)

| Phase | Description | Key Output |
|-------|-------------|-----------|
| **1** | **Universal Incident Model** — `IncidentEvent` typed model, Pydantic V2 validators, full pytest coverage | `incident_event.py` · `tests/test_incident_event.py` |
| **2** | **Ingestion + Normalization Layer** — pluggable normalizers for Spring Boot, Kafka, generic webhooks; FastAPI `/ingest/*` endpoints | `normalizers/` · `POST /ingest/http-log` · `/ingest/kafka-event` · `/ingest/webhook` |
| **3** | **Batch Analysis Engine** — Redis Streams accumulator, time-window grouping, single OpenAI batch call per window instead of per event | `batch_analyzer.py` · Redis Streams consumer |
| **4** | **RAG on Normalized History** — pgvector search on normalized incident history; system learns from resolved incidents over time | `pgvector/pgvector:pg16` migration · similarity search on `IncidentEvent` embeddings |

---

## About

Built by **[Tendresse Dutra](https://linkedin.com/in/tendresse-dutra)** — Backend & AI Systems Engineer.

Focus: distributed systems where operational intelligence is treated as a first-class concern — observable, resilient, and autonomous. This project grew from a specific LLM pipeline quality gate into a general-purpose AIOps intelligence layer, grounded in real production experience with high-traffic event-driven architectures.
