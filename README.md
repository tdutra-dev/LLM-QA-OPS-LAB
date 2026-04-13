# LLM-QA-OPS-LAB

[![CI](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml/badge.svg)](https://github.com/tdutra-dev/LLM-QA-OPS-LAB/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green)
![Tests](https://img.shields.io/badge/tests-278%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**AIOps Intelligence Layer — Universal Incident Ingestion, Batch LLM Analysis & RAG Faithfulness Evaluation**

A production-grade distributed system that intercepts incidents from any production system (Spring Boot, Kafka, webhooks), normalizes them into a universal typed model, buffers them in Redis Streams by time window, and analyzes the full batch with a single LLM call — producing structured awareness, root cause classification, and remediation suggestions. A built-in **LLM Evaluation layer** then measures whether the AI output is actually grounded in the data it received.

Built as a cross-language monorepo (TypeScript + Python) following the operational discipline of enterprise distributed systems.

---

## The Problem This Solves

In any company with multiple services in production:

- **500+ alerts per day** from different systems, each in a different format
- **Operators see noise**, not patterns — the real issue hides in the correlation
- **Calling an LLM per event** is slow, expensive, and context-blind
- **Existing tools** (PagerDuty, Splunk, BigPanda) are proprietary, expensive, and don't natively use LLMs for semantic root cause analysis

LLM-QA-OPS-LAB answers: *"given everything that happened in the last 5 minutes across all your services — what is actually wrong, what should you do, and how confident can we be in that analysis?"*

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ANY SYSTEM IN PRODUCTION                          │
│  Java Spring Boot · Kafka · MySQL · Node.js · AWS · Python services  │
│              HTTP webhooks  or  event-driven streams                 │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                                 │
│   POST /ingest/http-log     ← SpringBootNormalizer                  │
│   POST /ingest/kafka-event  ← KafkaNormalizer                       │
│   POST /ingest/webhook      ← WebhookNormalizer (PagerDuty, GitHub) │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                   NORMALIZATION LAYER                                │
│   Every source format → IncidentEvent (universal Pydantic V2 model) │
│   SpringBootNormalizer · KafkaNormalizer · WebhookNormalizer         │
│   Strategy pattern — each source is a pluggable normalizer           │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│               ACCUMULATOR — Redis Streams (XADD/XRANGE)              │
│   Buffer by time window (default: 5 min) · max 10,000 events        │
│   GET /stream/status — inspect queue depth before triggering batch   │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓  one call for the whole window, not one per event
┌──────────────────────────────────────────────────────────────────────┐
│                   BATCH LLM ANALYSIS ENGINE                          │
│   POST /batch/analyze — single gpt-4o-mini call on full window       │
│   → overall_assessment · critical_pattern · recommended_actions      │
│   → hallucination_risk (low/medium/high) · confidence_score (0-100) │
│   Graceful fallback: rule-based aggregation if no OPENAI_API_KEY     │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                   LLM EVALUATION LAYER                               │
│   POST /batch/faithfulness — was the LLM analysis grounded?         │
│   Rule-based grounding checks (always):                              │
│     · services_affected ⊆ real services in events?                  │
│     · incident_types ⊆ real types observed?                          │
│     · critical_pattern references real entities?                     │
│     · severity assessment consistent with event distribution?        │
│   Optional LLM judge (gpt-4o-mini): faithfulness_score = (rule+llm)÷2│
│   Output: faithfulness_score (0-100) · verdict (faithful/partial/   │
│           hallucinated) · ungrounded_claims[]                        │
└──────────────────────┬───────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                 │
│   Structured JSON · Prometheus metrics · Grafana dashboard           │
│   Autonomous remediation via LangGraph StateGraph (restart/scale/alert)│
│   Slack / Jira / email — action_executor.py                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest/http-log` | Ingest a Spring Boot / HTTP application log |
| `POST` | `/ingest/kafka-event` | Ingest a Kafka consumer event |
| `POST` | `/ingest/webhook` | Ingest any webhook (PagerDuty, GitHub Actions, Alertmanager, generic) |

### Batch Analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/batch/analyze` | Drain Redis Stream window → single LLM batch analysis |
| `GET`  | `/stream/status` | Redis Stream queue depth and availability |
| `POST` | `/batch/faithfulness` | Evaluate whether a batch analysis result is grounded in the events |

### Evaluation (original LLM pipeline quality gate)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate` | Rule-based incident evaluation |
| `POST` | `/evaluate/tool-call` | AI-driven evaluation (OpenAI function calling) |
| `POST` | `/evaluate/rag` | RAG-enhanced evaluation with similar incidents (pgvector) |
| `POST` | `/agent/start` | Start the autonomous LangGraph remediation agent |
| `POST` | `/agent/stop` | Stop the agent loop |
| `GET`  | `/agent/status` | Agent activity and iteration metrics |

### Observability

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health |
| `GET` | `/metrics` | Real-time KPIs |
| `GET` | `/analytics` | Pandas/Polars aggregations |
| `GET` | `/actions` | Action execution history |
| `GET` | `/prometheus-metrics` | Prometheus scraping endpoint |

Interactive docs: `http://localhost:8010/docs`

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic V2 |
| **AI / LLM** | OpenAI GPT-4o-mini · Function Calling · Structured Outputs (`response_format=json_object`) |
| **Agentic** | LangGraph `StateGraph` · typed state · `MemorySaver` checkpointing |
| **RAG** | pgvector (`<=>` cosine, 1536 dims) · OpenAI `text-embedding-3-small` · LlamaIndex |
| **LLM Evaluation** | Grounding checks (rule-based) · LLM-as-judge (gpt-4o-mini) · faithfulness score · hallucination rate |
| **Ingestion** | HTTP webhooks · Kafka events · PagerDuty / GitHub / Alertmanager webhooks · Strategy pattern normalizers |
| **Stream Buffer** | Redis Streams (XADD / XRANGE / XLEN) · time-window drain · graceful degradation |
| **Frontend** | Dash · Plotly · Bootstrap 5 |
| **Analytics** | Pandas · Polars |
| **Database** | PostgreSQL 16 + pgvector extension (`pgvector/pgvector:pg16`) · 4800+ embeddings · Redis 7 |
| **Observability** | Prometheus · Grafana · 13 custom metrics · SLO alerting rules |
| **Infrastructure** | Docker Compose · Kubernetes · Kustomize · nginx Ingress · NetworkPolicy |
| **CI/CD** | GitHub Actions · ruff · pytest (278 tests) · vitest · Trivy (filesystem CVE scan) · GHCR image push |
| **TypeScript** | pnpm workspaces · Zod · Vitest · ESLint |

---

## Quick Start

### Local (Docker Compose)

```bash
git clone https://github.com/tdutra-dev/LLM-QA-OPS-LAB.git
cd LLM-QA-OPS-LAB

# Copy and fill your OpenAI key
cp .env.example .env

# Start full stack
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
```

### Run Tests

```bash
cd packages/eval-py
pip install -e ".[dev]"
pytest tests/ -v   # 278 tests, zero external dependencies
```

---

## Ingestion Layer

Three normalizers implement the `Normalizer` Protocol (Strategy pattern):

**`SpringBootNormalizer`** — maps Java log levels to severity, extracts service from logger name, identifies exception class as error type.

**`KafkaNormalizer`** — handles epoch-millisecond timestamps, extracts service from headers or consumer group, parses error type from error text.

**`WebhookNormalizer`** — auto-detects source format from payload shape (PagerDuty `incident` envelope, Alertmanager `alerts[]` array, GitHub `action` field, or generic fallback).

```python
# Ingest a Spring Boot log
POST /ingest/http-log
{
  "level": "ERROR",
  "logger": "com.company.checkout.PaymentService",
  "message": "NullPointerException in processPayment",
  "timestamp": "2026-04-13T10:00:00Z"
}

# Response
{
  "incident_id": "inc_4a2b1c3d",
  "source_system": "spring-boot",
  "severity": "high",
  "service": "PaymentService",
  "incident_type": "technical_error",
  "stream_id": "1713009600000-0"
}
```

---

## Batch Analysis Engine

Instead of calling the LLM once per event (expensive, context-blind), the batch analyzer reads the entire Redis Stream window and sends all events in a single prompt:

```python
# Analyze the last 5 minutes
POST /batch/analyze?window_seconds=300

# Response
{
  "batch_id": "batch_f3a2c1b0",
  "event_count": 47,
  "services_affected": ["checkout-api", "payment-service"],
  "overall_assessment": "Cascading failure between checkout and payment services...",
  "critical_pattern": "checkout-api timeouts triggering payment-service retries",
  "recommended_actions": ["Rollback last checkout-api deployment", "Check DB connections"],
  "hallucination_risk": "low",
  "confidence_score": 88,
  "llm_used": true
}
```

The `hallucination_risk` and `confidence_score` fields are the LLM's self-assessment — directly tracked as Prometheus metrics.

---

## LLM Evaluation Layer

After every batch analysis, the faithfulness evaluator measures whether the LLM's claims are grounded in the actual events it received:

```python
POST /batch/faithfulness
{
  "batch_result": { ...BatchAnalysisResult... },
  "events": [ ...raw events from the stream window... ]
}

# Response
{
  "faithfulness_score": 92,
  "verdict": "faithful",
  "rule_checks": {
    "services_grounded_ratio": 1.0,
    "incident_types_grounded_ratio": 1.0,
    "critical_pattern_references_real_entity": true,
    "severity_assessment_consistent": true
  },
  "ungrounded_claims": [],
  "llm_used": false
}
```

**Scoring weights** (rule-based, always deterministic):
- `services_grounded_ratio` → 40 pts (are the services_affected real?)
- `incident_types_grounded_ratio` → 30 pts (are the incident types real?)
- `critical_pattern_references_real_entity` → 10 pts
- `severity_assessment_consistent` → 20 pts

If `OPENAI_API_KEY` is set, an independent LLM judge (gpt-4o-mini) also evaluates the report. Final score = `(rule_score + llm_score) // 2`.

---

## RAG Pipeline

The original evaluation pipeline generates a 1536-dim OpenAI embedding for every incident and stores it in PostgreSQL via the `pgvector` extension.

**`POST /evaluate/rag`** retrieves the top-K most similar historical incidents (cosine distance), builds a structured context, and enriches the LLM evaluation:

```sql
-- Cosine similarity search
SELECT record_id, embedding <=> :query_embedding AS distance
FROM evaluation_records
WHERE embedding IS NOT NULL
ORDER BY distance LIMIT :top_k
```

A higher-level **LlamaIndex pipeline** (`rag_llamaindex.py`) wraps the same pgvector store with `VectorStoreIndex` + `IngestionPipeline` + `QueryEngine` for GPT-4o-mini summarization of historical patterns.

> **Note**: pgvector requires `pgvector/pgvector:pg16` image (not plain `postgres:16-alpine`). This is set correctly in `docker-compose.yml`.

---

## Observability

13 custom Prometheus metrics at `GET /prometheus-metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `llmqa_eval_requests_total` | Counter | Evaluation requests by status |
| `llmqa_eval_score` | Histogram | Score distribution (0–100) |
| `llmqa_rag_retrieval_latency_seconds` | Histogram | pgvector query latency |
| `llmqa_rag_embedding_latency_seconds` | Histogram | OpenAI embedding latency |
| `llmqa_rag_similar_incidents_found` | Histogram | Similar incidents retrieved per request |
| `llmqa_rag_requests_total` | Counter | RAG requests by outcome (hit / miss) |
| `llmqa_agent_loop_iterations_total` | Counter | LangGraph agent loop cycles |
| `llmqa_agent_loop_errors_total` | Counter | Agent loop failures |
| `llmqa_action_executor_total` | Counter | Autonomous actions by type and outcome |
| `llmqa_batch_analysis_total` | Counter | Batch analysis runs by hallucination_risk + llm_used |
| `llmqa_batch_stream_events` | Histogram | Events analyzed per batch run |
| `llmqa_rag_faithfulness_score` | Histogram | Faithfulness score distribution (0–100) |
| `llmqa_faithfulness_total` | Counter | Faithfulness evaluations by verdict |

**SLO alerting rules** (`prometheus/alerts/slo.yml`):
- Availability: error rate < 1% per 5-minute window
- Latency: `/evaluate` p95 < 500ms · `/evaluate/rag` p95 < 300ms
- RAG hit rate > 60%
- Agent loop must execute at least once every 10 minutes

---

## CI/CD Pipeline

```
push to main / PR
    │
    ├── lint-py  (ruff)       eval-py + dash-app Python code
    ├── test-py  (pytest)     278 unit tests, offline (DB_URL="" REDIS_URL="")
    ├── lint-ts  (eslint)     TypeScript packages
    ├── test-ts  (vitest)     TypeScript packages
    │
    └── [on green] ─► docker-build ─► push eval-py + dash-app to GHCR (main)
                    └─► security-scan (Trivy fs scan — CRITICAL/HIGH CVE check)
```

---

## Project History — Steps 1–14 + Phases 1–4

### Original LLM Pipeline Quality Gate (Steps 1–14)

| Step | Description | Key Technologies |
|------|-------------|-----------------|
| 1 | Monorepo architecture | pnpm workspaces, TypeScript, FeatureSpec domain |
| 2 | TestCase domain model | Fixtures, e-commerce checkout flow |
| 3 | LLM Adapter abstraction | Adapter pattern, MockLLMAdapter |
| 4 | Versioned Prompt Engine | Markdown templates, Zod validation |
| 5 | End-to-end test generation | FeatureSpec → LLM → TestCase[] pipeline |
| 6 | Production resilience layer | Retry/backoff, Timeout, Fallback, safe JSON parsing |
| 7 | KPI & Health Scoring | p50/p95/p99 latency, HEALTHY/DEGRADED/CRITICAL |
| 8 | Alert Engine + Incident Copilot | AlertEngine, OpenAI GPT-4o-mini reports |
| 9 | Runtime Simulator + Python service | FastAPI, Pydantic, cross-language contracts |
| 10 | Complete backend stack | PostgreSQL, Redis, Pandas, Polars, ActionExecutor |
| 11 | Kubernetes deployment | 18 manifests, Kustomize, multi-stage Dockerfile |
| 12 | RAG + Prometheus observability | pgvector, embeddings, 9 custom metrics, Grafana |
| 13 | LlamaIndex + CI/CD + Security | LlamaIndex, GitHub Actions, Trivy, NetworkPolicy |
| 14 | LangGraph agentic pipeline | StateGraph, TypedDict state, MemorySaver checkpointing |

### Universal AIOps Intelligence Layer (Phases 1–4) — Completed

| Phase | Description | Files | Tests |
|-------|-------------|-------|-------|
| **1** | **Universal Incident Model** — `IncidentEvent` with Pydantic V2 validators, `derive_incident_type()`, `to_standard_incident()` bridge | `incident_event.py` | 56 |
| **2** | **Ingestion + Normalization Layer** — SpringBoot/Kafka/Webhook normalizers (Strategy pattern), `/ingest/*` endpoints | `normalizers.py` | 78 |
| **3** | **Batch LLM Analyzer** — Redis Streams buffer (XADD/XRANGE), time-window drain, single gpt-4o-mini call, `hallucination_risk` + `confidence_score` metrics | `stream_buffer.py` · `batch_analyzer.py` | 82 |
| **4** | **RAG Faithfulness Evaluator** — rule-based grounding checks + optional LLM judge, `faithfulness_score` + `verdict` Prometheus metrics, pgvector image fix | `rag_faithfulness.py` | 62 |

---

## About

Built by **[Tendresse Dutra](https://linkedin.com/in/tendresse-dutra)** — Backend & AI Systems Engineer.

Focus: distributed systems where AI quality is treated as a first-class operational concern — observable, measurable, and resilient. This project grew from a specific LLM pipeline quality gate into a general-purpose AIOps intelligence layer with a built-in LLM evaluation framework, grounded in real production experience with high-traffic event-driven architectures.


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
