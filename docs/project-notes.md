# Project Notes — LLM-QA-OPS-LAB

Appunti progettuali, materiale CV e note per interviste.

---

## 13-Step Roadmap — Recap Tecnico

### Step 1 — Architettura Monorepo
Setup del workspace TypeScript con `pnpm workspaces`. Definizione del dominio `FeatureSpec` (specifiche delle feature da testare). Fondamenta dell'intero progetto.

### Step 2 — Domain Model: TestCase
Modello `TestCase` con fixture reale per il flusso di checkout e-commerce. Primo dato concreto del sistema di QA.

### Step 3 — LLM Adapter Abstraction
Interfaccia `LLMAdapter` con implementazione `MockLLMAdapter` deterministica. Pattern Adapter per isolare il codice business dall'AI provider. Testabile senza API reale.

### Step 4 — Prompt Engine Versionato
Sistema `PromptEngine` con versioning dei prompt via Markdown. Schema validation con Zod sull'output del modello. Primo safety layer sull'output LLM.

### Step 5 — Pipeline End-to-End di Generazione Test
Prima pipeline completa: `FeatureSpec → LLM → TestCase[]` con validazione schema. Il sistema è già in grado di generare test case autonomamente.

### Step 6 — Production Resilience Layer
Tre pattern di resilienza implementati in TypeScript:
- **Retry** con backoff esponenziale
- **Timeout** con `AbortController`
- **Fallback** su modello alternativo
- **Safe JSON parsing** con recovery da output malformato

> Tema chiave per interviste: *"Come rendi un sistema LLM affidabile in produzione?"*

### Step 7 — Observability: KPIs e Health Scoring
Calcolo KPI real-time: success rate, latency percentili (p50/p95/p99), error rate. Algoritmo `computeWorkflowHealth` che produce score `HEALTHY / DEGRADED / CRITICAL`. Base per tutto l'alerting successivo.

### Step 8 — Alert Engine + Incident Copilot
- **AlertEngine** con regole configurabili, cooldown per evitare alert storm
- **IncidentCopilot** integrato con **OpenAI GPT-4o-mini**: analizza gli alert `CRITICAL` e genera report strutturati con root cause + remediation steps in linguaggio operativo

> Tema chiave: *"LLM che monitora altri sistemi LLM"*

### Step 9 — Runtime Simulator + Python Microservice
- **Simulatore** TypeScript che genera eventi di runtime con fault injection controllata
- **Pacchetto `contracts`** con tipi condivisi TypeScript/Python
- **FastAPI service** (`eval-py`) in Python con Pydantic — primo servizio cross-language del sistema

### Step 10 — Backend Completo: Persistenza, Cache, Analytics e Autonomia
Stack backend production-ready:
- **PostgreSQL** con SQLAlchemy ORM per persistenza incidents/evaluations
- **Redis** cache-aside layer per metrics e analytics (TTL-based)
- **Pandas + Polars** analytics endpoint per aggregazioni sui dati storici
- **ActionExecutor**: componente autonomo che esegue azioni di remediation (restart, scale, alert) in base ai KPIs — *sistema che si ripara da solo*

### Step 11 — Kubernetes Deployment
Infrastruttura completa per deployment production:
- **18 manifest K8s**: Namespace, ConfigMap, Secret, PVC, Deployments, Services, Ingress
- **Kustomize** per gestione multi-environment
- **Dockerfile multi-stage** per `dash-app` (Python, non-root, optimized)
- **Script di management** con auto-detection `kind`/`minikube`

### Step 12 — RAG-Enhanced Evaluation + Prometheus Observability
Obiettivo: arricchire il motore di valutazione con contesto storico reale (RAG) e misurarne l'impatto con metriche Prometheus.

**RAG con pgvector (`rag_retriever.py`):**
- `pgvector` extension su PostgreSQL: colonna `embedding VECTOR(1536)` su `evaluation_records`
- Genera embedding dell'incident via OpenAI `text-embedding-3-small`, esegue similarity search con l'operatore `<=>` (cosine distance), restituisce i top-K incident più simili
- `POST /evaluate/rag`: nuovo endpoint che restituisce `similarIncidents[]`, `ragContextUsed`, `embeddingStored`
- Graceful degradation: senza `OPENAI_API_KEY` o pgvector, si comporta come `/evaluate` standard — nessun crash
- Embedding auto-salvato ad ogni `store.save()` per costruire il knowledge base progressivamente
- Nuovi modelli Pydantic: `SimilarIncidentResponse` + `RagEvaluationResult`

**Prometheus Observability (`metrics.py`):**
- 9 metriche custom: `llmqa_eval_requests_total`, `llmqa_eval_score`, `llmqa_rag_retrieval_latency_seconds`, `llmqa_rag_embedding_latency_seconds`, `llmqa_rag_similar_incidents_found`, `llmqa_rag_requests_total`, `llmqa_agent_loop_iterations_total`, `llmqa_agent_loop_errors_total`, `llmqa_action_executor_total`
- `prometheus-fastapi-instrumentator`: auto-instrumentazione di tutti gli endpoint (p50/p95/p99)
- `GET /prometheus-metrics`: endpoint scraping per Prometheus
- Graceful degradation: no-op stubs se `prometheus_client` non è installato

**Dipendenze aggiunte:** `pgvector>=0.3`, `prometheus-client>=0.20`, `prometheus-fastapi-instrumentator>=7.0`

> Tema chiave: *"RAG non come black box, ma come componente osservabile — misuri retrieval latency, hit rate, e vedi l'impatto sul score direttamente su Grafana"*

### Step 13 — LlamaIndex RAG Pipeline + CI/CD + Production Readiness
Obiettivo: refactoring del RAG layer con LlamaIndex, CI/CD automatizzato, SLO quantitativi con Grafana e security hardening K8s.

**LlamaIndex RAG Pipeline (`rag_llamaindex.py`):**
- `VectorStoreIndex` backed da `PGVectorStore` (stesso PostgreSQL/pgvector di Step 12)
- `IngestionPipeline` per indicizzare nuovi incident come `TextNode` con metadata strutturata
- `VectorIndexRetriever` — alternativa più ricca a `find_similar_incidents()` con `NodeWithScore`
- `summarize_similar_incidents()` — QueryEngine che genera summary GPT-4o-mini sui pattern storici
- Pacchetto opzionale: `pip install eval-py[llamaindex]` — zero breaking changes

**Test suite (`tests/test_step13.py` + `conftest.py`):**
- 19 test unit, zero dipendenze esterne (no PostgreSQL, no Redis, no OpenAI in CI)
- Copertura: engine, Pydantic models, RAG retriever, metrics, LlamaIndex pipeline
- `conftest.py`: fixture `no_openai_key` (autouse) per esecuzione offline sicura

**GitHub Actions CI/CD (`.github/workflows/ci.yml`):**
- Job `lint-py`: ruff su eval-py + dash-app
- Job `test-py`: pytest offline (no OPENAI_API_KEY, no DB)
- Job `lint-ts` + `test-ts`: ESLint + vitest su pacchetti TypeScript
- Job `docker-build`: build eval-py + dash-app images; **push su GHCR solo su merge a main**
- Job `security-scan`: Trivy container scan → risultati in GitHub Security tab (SARIF)
- Gate: docker-build dipende da lint-py + test-py — nessun deploy senza green CI

**Prometheus + Grafana (Step 13 observability stack):**
- `prometheus/prometheus.yml`: scraping eval-py `/prometheus-metrics` ogni 15s
- `prometheus/alerts/slo.yml`: 9 alerting rules — HighErrorRate, ServiceDown, EvaluateLatencyHigh, RagEvaluateLatencyHigh, RagRetrievalLatencyCritical, RagHitRateLow, HighCriticalIncidentRate, AverageScoreCriticallyLow, AgentLoopStalled
- `prometheus/grafana/`: datasource auto-provisioning + dashboard JSON con 10 panel (eval metrics, RAG metrics, HTTP latency SLO, agent loop health)
- `docker-compose.yml`: `prometheus:9090` + `grafana:3000` con volume persistenti

**SLO quantitativi definiti:**
- Availability: error rate < 1% / 5-minute window
- Latency: `/evaluate` p95 < 500ms, `/evaluate/rag` p95 < 300ms, retrieval p95 < 200ms
- RAG quality: hit rate > 60%
- Agent health: iterations > 0 ogni 10 minuti

**Security hardening K8s (`k8s/network-policy.yaml`):**
- NetworkPolicy per ogni pod: eval-py, postgres, redis, dash-app
- Least-privilege: postgres/redis accettano ingress SOLO da eval-py, egress vuoto
- eval-py: egress a postgres:5432, redis:6379, internet:443 (OpenAI), DNS:53
- Trivy container scanning integrato nel CI/CD pipeline

> Tema chiave: *"Stack completo della job offer: RAG + pgvector + LlamaIndex + CI/CD gate + SLO monitorati su Grafana + security hardening — sistema AI production-ready con ogni layer osservabile, testabile e protetto"*

---

## Messaggi Chiave per CV e Interviste

| Tema | Come Dirlo |
|------|-----------|
| **Stack** | TypeScript monorepo + Python FastAPI + PostgreSQL + pgvector + Redis + Kubernetes |
| **Sfida Principale** | Rendere sistemi LLM osservabili, resilienti e autonomi in produzione |
| **Innovazione** | LLM che monitora se stesso, genera azioni correttive e migliora con la storia (RAG) |
| **Pattern Applicati** | Adapter, Retry/Timeout/Fallback, Cache-Aside, Observer, Command, RAG |
| **Cross-Language** | Contratti condivisi TypeScript/Python con Pydantic + Zod |
| **Observability** | Prometheus metriche custom + auto-instrumentazione FastAPI + SLO quantitativi |

---

## Descrizione Progetto per CV

### Versione Italiana (bilanciata)
> Sistema distribuito production-grade che implementa un agente AI autonomo per il monitoraggio e la remediation di pipeline LLM. L'agente percepisce incidenti in real-time, li valuta tramite **OpenAI function calling**, recupera contesto storico rilevante tramite **RAG con pgvector** e orchestra azioni correttive automatiche — architettura cross-language TypeScript + Python con resilience patterns (retry, timeout, fallback), persistenza PostgreSQL, cache Redis, deployment Kubernetes e osservabilità Prometheus.
>
> `TypeScript · Python · FastAPI · PostgreSQL · pgvector · Redis · OpenAI API · RAG · LlamaIndex · Pandas · Polars · Dash · Prometheus · Docker · Kubernetes`

### Versione Inglese (bilanciata)
> Production-grade distributed system implementing an autonomous AI agent for LLM pipeline monitoring and remediation. The agent perceives incidents in real-time, evaluates them via **OpenAI function calling**, retrieves relevant historical context through **RAG with pgvector**, and orchestrates corrective actions automatically — cross-language architecture TypeScript + Python with resilience patterns (retry, timeout, fallback), PostgreSQL persistence, Redis cache, Kubernetes deployment, and Prometheus observability.
>
> `TypeScript · Python · FastAPI · PostgreSQL · pgvector · Redis · OpenAI API · RAG · LlamaIndex · Pandas · Polars · Dash · Prometheus · Docker · Kubernetes`

---

## CV Completo — Versione Italiana

### Tendresse Dutra de Carvalho
**Backend & AI Systems Engineer** · API · Sistemi Distribuiti · LLM Operations
linkedin.com/in/tendresse-dutra · github.com/tdutra-dev

**Lingue:** Italiano: Bilingue · Inglese: Avanzato – Professionale · Portoghese: Madrelingua

### Profilo
Senior Software Engineer specializzata in sistemi backend distribuiti e piattaforme AI production-grade. Progetto sistemi in cui i componenti LLM sono trattati come servizi operativi: osservabili, resilienti e autonomi. Focus attuale su AI reliability, operational intelligence e automazione decisionale.

### Competenze Tecniche
**Backend:** Node.js · TypeScript · Python · Java (Spring Boot/WebFlux) · C# (.NET) · FastAPI · SQLAlchemy
**Database:** PostgreSQL · MySQL · MongoDB · SQL Server · Redis
**Infrastruttura:** Docker · Kubernetes · Kafka · Architetture Event-Driven · Microservizi · CI/CD
**AI/LLM:** OpenAI API · Function Calling · Structured Outputs · Prompt Engineering · RAG · pgvector · LlamaIndex · AI Reliability
**Analytics:** Pandas · Polars · Dash · Plotly · Analisi Time-Series · Elasticsearch
**Observability:** Prometheus · Grafana · Metriche Custom · SLO/SLA

### Esperienza

**Software Engineer — Swag International** *(Crypto Exchange, 2022–2025)*
- Microservizi backend in produzione per piattaforma fintech/crypto (Java Spring Boot, MySQL)
- Flussi event-driven con Kafka/Confluent per integrazione tra sistemi distribuiti
- Stack di osservabilità con Elasticsearch e logging strutturato
- Bot Telegram per comunicazione dati statistici; integrazioni transazionali via Customer.io

**Backend Developer — Analytics Intelligence, Next4B** *(2022)*
- API backend Python e data layer MongoDB per dashboard di reportistica finanziaria
- Pipeline di elaborazione e aggregazione dati per analytics e grafici destinati ai clienti

**Systems Analyst / Backend Developer — I.CON** *(2019–2021)*
- Backend C#/.NET per piattaforma di gestione operativa aeroportuale
- Focus su affidabilità operativa e ottimizzazione interfacce interne

**Backend Developer — Cegeka** *(2017–2019)*
- Componenti backend C#/.NET per sistemi enterprise, workflow interni e manutenzione servizi

**Systems Analyst — FIAT** *(Italia & Brasile, 2014–2017)*
- Sistemi backend C#/.NET su larga scala; ottimizzazione stored procedures e job SQL Server per performance e affidabilità dei flussi dati

### Formazione
**Computer Science** — FUMEC University, Brasile *(2008–2015)*
**Formazione continua:** Apache Kafka · Spring WebFlux · Node.js / NestJS / TypeScript

---

## CV Completo — Versione Inglese

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
