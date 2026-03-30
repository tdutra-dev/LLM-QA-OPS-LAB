# Project Notes — LLM-QA-OPS-LAB

Design notes, CV material, and interview preparation.

---

## 13-Step Roadmap — Technical Recap

### Step 1 — Monorepo Architecture
TypeScript workspace setup with `pnpm workspaces`. Domain definition of `FeatureSpec` (specs for features under test). Foundation of the entire project.

### Step 2 — Domain Model: TestCase
`TestCase` model with a real fixture for an e-commerce checkout flow. First concrete piece of data in the QA system.

### Step 3 — LLM Adapter Abstraction
`LLMAdapter` interface with a deterministic `MockLLMAdapter` implementation. Adapter pattern to isolate business logic from the AI provider. Fully testable without a real API.

### Step 4 — Versioned Prompt Engine
`PromptEngine` system with Markdown-based prompt versioning. Zod schema validation on model output. First safety layer on LLM output.

### Step 5 — End-to-End Test Generation Pipeline
First complete pipeline: `FeatureSpec → LLM → TestCase[]` with schema validation. The system is already capable of generating test cases autonomously.

### Step 6 — Production Resilience Layer
Three resilience patterns implemented in TypeScript:
- **Retry** with exponential backoff
- **Timeout** with `AbortController`
- **Fallback** to an alternative model
- **Safe JSON parsing** with recovery from malformed output

> Key interview topic: *"How do you make an LLM system reliable in production?"*

### Step 7 — Observability: KPIs and Health Scoring
Real-time KPI computation: success rate, latency percentiles (p50/p95/p99), error rate. `computeWorkflowHealth` algorithm producing a `HEALTHY / DEGRADED / CRITICAL` score. Foundation for all subsequent alerting.

### Step 8 — Alert Engine + Incident Copilot
- **AlertEngine** with configurable rules and cooldown to prevent alert storms
- **IncidentCopilot** integrated with **OpenAI GPT-4o-mini**: analyzes `CRITICAL` alerts and generates structured reports with root cause + remediation steps in operational language

> Key topic: *"LLM monitoring other LLM systems"*

### Step 9 — Runtime Simulator + Python Microservice
- TypeScript **Simulator** generating runtime events with controlled fault injection
- **`contracts` package** with shared TypeScript/Python types
- **FastAPI service** (`eval-py`) in Python with Pydantic — first cross-language service in the system

### Step 10 — Complete Backend: Persistence, Cache, Analytics, and Autonomy
Production-ready backend stack:
- **PostgreSQL** with SQLAlchemy ORM for incidents/evaluations persistence
- **Redis** cache-aside layer for metrics and analytics (TTL-based)
- **Pandas + Polars** analytics endpoint for historical data aggregations
- **ActionExecutor**: autonomous component that executes remediation actions (restart, scale, alert) based on KPIs — *a system that repairs itself*

### Step 11 — Kubernetes Deployment
Complete infrastructure for production deployment:
- **18 K8s manifests**: Namespace, ConfigMap, Secret, PVC, Deployments, Services, Ingress
- **Kustomize** for multi-environment management
- **Multi-stage Dockerfile** for `dash-app` (Python, non-root, optimized)
- **Management scripts** with `kind`/`minikube` auto-detection

### Step 12 — RAG-Enhanced Evaluation + Prometheus Observability
Goal: enrich the evaluation engine with real historical context (RAG) and measure its impact with Prometheus metrics.

**RAG with pgvector (`rag_retriever.py`):**
- `pgvector` extension on PostgreSQL: `embedding VECTOR(1536)` column on `evaluation_records`
- Generates incident embeddings via OpenAI `text-embedding-3-small`, runs similarity search with the `<=>` (cosine distance) operator, returns the top-K most similar incidents
- `POST /evaluate/rag`: new endpoint returning `similarIncidents[]`, `ragContextUsed`, `embeddingStored`
- Graceful degradation: without `OPENAI_API_KEY` or pgvector, behaves like `/evaluate` standard — no crashes
- Embeddings auto-saved on every `store.save()` to progressively build the knowledge base
- New Pydantic models: `SimilarIncidentResponse` + `RagEvaluationResult`

**Prometheus Observability (`metrics.py`):**
- 9 custom metrics: `llmqa_eval_requests_total`, `llmqa_eval_score`, `llmqa_rag_retrieval_latency_seconds`, `llmqa_rag_embedding_latency_seconds`, `llmqa_rag_similar_incidents_found`, `llmqa_rag_requests_total`, `llmqa_agent_loop_iterations_total`, `llmqa_agent_loop_errors_total`, `llmqa_action_executor_total`
- `prometheus-fastapi-instrumentator`: auto-instrumentation of all endpoints (p50/p95/p99)
- `GET /prometheus-metrics`: scraping endpoint for Prometheus
- Graceful degradation: no-op stubs if `prometheus_client` is not installed

**Added dependencies:** `pgvector>=0.3`, `prometheus-client>=0.20`, `prometheus-fastapi-instrumentator>=7.0`

> Key topic: *"RAG not as a black box, but as an observable component — you measure retrieval latency, hit rate, and see the impact on score directly in Grafana"*

### Step 13 — LlamaIndex RAG Pipeline + CI/CD + Production Readiness
Goal: refactor the RAG layer with LlamaIndex, automated CI/CD, quantitative SLOs with Grafana, and K8s security hardening.

**LlamaIndex RAG Pipeline (`rag_llamaindex.py`):**
- `VectorStoreIndex` backed by `PGVectorStore` (same PostgreSQL/pgvector as Step 12)
- `IngestionPipeline` to index new incidents as `TextNode` with structured metadata
- `VectorIndexRetriever` — richer alternative to `find_similar_incidents()` with `NodeWithScore`
- `summarize_similar_incidents()` — QueryEngine that generates GPT-4o-mini summaries on historical patterns
- Optional package: `pip install eval-py[llamaindex]` — zero breaking changes

**Test suite (`tests/test_step13.py` + `conftest.py`):**
- 19 unit tests, zero external dependencies (no PostgreSQL, no Redis, no OpenAI in CI)
- Coverage: engine, Pydantic models, RAG retriever, metrics, LlamaIndex pipeline
- `conftest.py`: `no_openai_key` fixture (autouse) for safe offline execution

**GitHub Actions CI/CD (`.github/workflows/ci.yml`):**
- Job `lint-py`: ruff on eval-py + dash-app
- Job `test-py`: pytest offline (no OPENAI_API_KEY, no DB)
- Job `lint-ts` + `test-ts`: ESLint + vitest on TypeScript packages
- Job `docker-build`: build eval-py + dash-app images; **push to GHCR only on merge to main**
- Job `security-scan`: Trivy container scan → results in GitHub Security tab (SARIF)
- Gate: docker-build depends on lint-py + test-py — no deploy without green CI

**Prometheus + Grafana (Step 13 observability stack):**
- `prometheus/prometheus.yml`: scraping eval-py `/prometheus-metrics` every 15s
- `prometheus/alerts/slo.yml`: 9 alerting rules — HighErrorRate, ServiceDown, EvaluateLatencyHigh, RagEvaluateLatencyHigh, RagRetrievalLatencyCritical, RagHitRateLow, HighCriticalIncidentRate, AverageScoreCriticallyLow, AgentLoopStalled
- `prometheus/grafana/`: datasource auto-provisioning + dashboard JSON with 10 panels (eval metrics, RAG metrics, HTTP latency SLO, agent loop health)
- `docker-compose.yml`: `prometheus:9090` + `grafana:3000` with persistent volumes

**Defined quantitative SLOs:**
- Availability: error rate < 1% / 5-minute window
- Latency: `/evaluate` p95 < 500ms, `/evaluate/rag` p95 < 300ms, retrieval p95 < 200ms
- RAG quality: hit rate > 60%
- Agent health: iterations > 0 every 10 minutes

**K8s security hardening (`k8s/network-policy.yaml`):**
- NetworkPolicy for every pod: eval-py, postgres, redis, dash-app
- Least-privilege: postgres/redis accept ingress ONLY from eval-py, empty egress
- eval-py: egress to postgres:5432, redis:6379, internet:443 (OpenAI), DNS:53
- Trivy container scanning integrated in CI/CD pipeline

> Key topic: *"Complete stack matching the job offer: RAG + pgvector + LlamaIndex + CI/CD gate + SLOs monitored on Grafana + security hardening — production-ready AI system with every layer observable, testable, and protected"*

---

## Key Messages for CV and Interviews

| Topic | How to Express It |
|-------|------------------|
| **Stack** | TypeScript monorepo + Python FastAPI + PostgreSQL + pgvector + Redis + Kubernetes |
| **Main Challenge** | Making LLM systems observable, resilient, and autonomous in production |
| **Innovation** | LLM that monitors itself, generates corrective actions, and improves with history (RAG) |
| **Patterns Applied** | Adapter, Retry/Timeout/Fallback, Cache-Aside, Observer, Command, RAG |
| **Cross-Language** | Shared TypeScript/Python contracts with Pydantic + Zod |
| **Observability** | Custom Prometheus metrics + FastAPI auto-instrumentation + quantitative SLOs |

---

## Project Description for CV

### Balanced Version
> Production-grade distributed system implementing an autonomous AI agent for LLM pipeline monitoring and remediation. The agent perceives incidents in real-time, evaluates them via **OpenAI function calling**, retrieves relevant historical context through **RAG with pgvector**, and orchestrates corrective actions automatically — cross-language architecture TypeScript + Python with resilience patterns (retry, timeout, fallback), PostgreSQL persistence, Redis cache, Kubernetes deployment, and Prometheus observability.
>
> `TypeScript · Python · FastAPI · PostgreSQL · pgvector · Redis · OpenAI API · RAG · LlamaIndex · Pandas · Polars · Dash · Prometheus · Docker · Kubernetes`

---

## Full CV — English Version

### Tendresse Dutra de Carvalho
**Backend & AI Systems Engineer** · API · Distributed Systems · LLM Operations
linkedin.com/in/tendresse-dutra · github.com/tdutra-dev

**Languages:** Italian: Bilingual · English: Advanced – Professional · Portuguese: Native

### Profile
Senior Software Engineer specializing in distributed backend systems and production-grade AI platforms. I design and build systems where LLM components are treated as operational services: observable, resilient, and autonomous. Current focus on AI reliability, operational intelligence, and system-level decision automation.

### Technical Skills
**Backend:** Node.js · TypeScript · Python · Java (Spring Boot/WebFlux) · C# (.NET) · FastAPI · SQLAlchemy
**Database:** PostgreSQL · MySQL · MongoDB · SQL Server · Redis
**Infrastructure:** Docker · Kubernetes · Kafka · Event-Driven Architecture · Microservices · CI/CD
**AI/LLM:** OpenAI API · Function Calling · Structured Outputs · Prompt Engineering · RAG · pgvector · LlamaIndex · AI Reliability
**Analytics:** Pandas · Polars · Dash · Plotly · Time-Series Analysis · Elasticsearch
**Observability:** Prometheus · Grafana · Custom Metrics · SLO/SLA

### Experience

**Software Engineer — Swag International** *(Crypto Exchange, 2022–2025)*
- Backend microservices in production for a fintech/crypto platform (Java Spring Boot, MySQL)
- Event-driven pipelines with Kafka/Confluent for cross-system integration
- Observability stack with Elasticsearch and structured logging
- Telegram bots for statistical data reporting; transactional integrations via Customer.io

**Backend Developer — Analytics Intelligence, Next4B** *(2022)*
- Python backend APIs and MongoDB data layer for financial reporting dashboards
- Data processing and aggregation pipelines for client-facing analytics and charts

**Systems Analyst / Backend Developer — I.CON** *(2019–2021)*
- C#/.NET backend for an airport operations management platform
- Focus on operational reliability and internal interface optimization

**Backend Developer — Cegeka** *(2017–2019)*
- C#/.NET backend components for enterprise systems, internal workflow tooling and service maintenance

**Systems Analyst — FIAT** *(Italy & Brazil, 2014–2017)*
- C#/.NET backend systems at scale; SQL Server stored procedures and job optimization for data pipeline performance and reliability

### Education
**Computer Science** — FUMEC University, Brazil *(2008–2015)*
**Continuous Learning:** Apache Kafka · Spring WebFlux · Node.js / NestJS / TypeScript
