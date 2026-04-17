# Tendresse Dutra
**AI Backend Engineer · Python · LLMOps · Production AI Systems**
linkedin.com/in/tendresse-dutra · github.com/tdutra-dev
Open to full-time & freelance · Remote / Italy

**Languages:** Italian (bilingual) · English (professional) · Portuguese (native)

---

## Profile

Backend engineer with 10+ years in distributed systems.

I made a deliberate switch: from deterministic software — rigid inputs, predictable transformations, defined outputs — to probabilistic AI systems, where inputs are fuzzy, transformations reason over context, and outputs are emergent.

That shift changed how I think about reliability. In traditional systems, correctness is binary. In AI systems, you need pipelines that handle uncertainty gracefully: structured ingestion, grounded retrieval, observable behavior, and failure modes you can actually debug.

I build that infrastructure — agentic pipelines, batch LLM analysis with built-in faithfulness evaluation, RAG with pgvector, and the observability layer that makes probabilistic system behavior measurable and debuggable.

---

## Featured Project

**LLM-QA-OPS-LAB** — AIOps Intelligence Layer for Production Incident Analysis
github.com/tdutra-dev/LLM-QA-OPS-LAB

- **Ingestion layer**: accepts incidents from any source (Spring Boot, Kafka, webhooks), normalizes via pluggable validators, buffers in Redis Streams, and batches per time window — one LLM call per window; LLM self-reports hallucination risk and confidence score
- **LLM Evaluation layer**: faithfulness evaluator combining rule-based grounding checks with LLM-as-judge; classifies each batch as faithful, partially faithful, or hallucinated; tracked in Prometheus
- **RAG pipeline**: pgvector + LlamaIndex with cosine similarity — grounds LLM output in real historical incidents before each analysis
- **Agentic pipeline with LangGraph**: typed StateGraph across perceive → retrieve → evaluate → store → act → audit, with conditional routing and conversation memory
- **Observability**: custom Prometheus metrics covering hallucination rate, faithfulness distribution, RAG hit rate, and batch latency; SLO alerting, Grafana auto-provisioned
- **Production-ready**: full test suite with zero external dependencies, Docker, Kubernetes, Trivy CVE scan in CI
- **Cross-language monorepo**: Python (FastAPI, SQLAlchemy 2, Pydantic V2) + TypeScript (Zod, Vitest)

`Python · FastAPI · PostgreSQL · pgvector · Redis Streams · OpenAI API · LlamaIndex · LangGraph · LLMOps · Prometheus · Grafana · Docker · Kubernetes · TypeScript`

---

## Technical Skills

**AI / LLM:** OpenAI API · Function Calling · Structured Outputs · RAG · pgvector · LlamaIndex · LangGraph · Prompt Engineering · AIOps · LLMOps · Batch Event Analysis · Faithfulness Evaluation
**Python:** FastAPI · SQLAlchemy 2 · Pydantic V2 · Pandas · Pytest · Dash · Plotly
**TypeScript / Node.js:** Zod · Vitest · ESLint · NestJS
**Database:** PostgreSQL · Redis Streams · MySQL · MongoDB · SQL Server
**Observability:** Prometheus · Grafana · Elasticsearch
**Infrastructure:** Docker · Kubernetes · GitHub Actions · CI/CD · Kafka · Event-Driven · Microservices
**Backend:** Java (Spring Boot / WebFlux) · C# (.NET) · REST APIs

---

## Experience

**Software Engineer — Swag International** *(Crypto Exchange, 08/2022–2025)*
- Backend microservices in production for a fintech/crypto platform (Java Spring Boot, MySQL)
- Event-driven pipelines with Kafka/Confluent enabling real-time data sync across 12+ modules
- Observability stack with Elasticsearch and structured logging; alert-driven monitoring reducing mean time to incident detection from hours to minutes
- Automated statistical reporting via Telegram bots
- Transactional communication integrated with Customer.io — developed backend workflow and used Liquid reducing 60% of redundancy in email templates

**Backend Developer — Analytics Intelligence, Next4B** *(03/2022–07/2022)*
- Python backend APIs and MongoDB data layer for financial reporting dashboards
- Data processing and aggregation pipelines for client-facing analytics and charts
- Visualization and monitoring data with Grafana

**Prior experience — Systems Analyst & Backend Developer** *(2014–2021)*  
*I.CON, Cegeka, FIAT (Italy & Brazil)*

C#/.NET enterprise backends across airport operations, enterprise workflow systems, and automotive manufacturing at scale. Focus on system reliability, SQL Server performance optimization, and cross-country delivery.

---

## Education

**Computer Science** — FUMEC University, Brazil *(2008–2015)*
