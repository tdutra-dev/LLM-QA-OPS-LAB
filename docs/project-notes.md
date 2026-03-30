# Project Notes — LLM-QA-OPS-LAB

Appunti progettuali, materiale CV e note per interviste.

---

## 11-Step Roadmap — Recap Tecnico

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

### Step 12 — Performance Monitoring (prossimo)
Obiettivo: osservabilità production-grade con metriche quantitative e load testing.
- **Prometheus**: scraping metriche da FastAPI (endpoint `/metrics`), PostgreSQL, Redis
- **Grafana**: dashboard real-time con alert su soglie KPI (latency, error rate, throughput)
- **Latency percentili**: p50/p95/p99 per ogni endpoint e per l'agent loop
- **Load testing**: k6 o Locust per simulare carico e validare comportamento sotto stress
- **Alerting rules**: notifiche su degradazione delle performance prima che diventi critico

> Tema chiave: *"Come misuri e provi che il sistema regge in produzione?"*

### Step 13 — Production Readiness & SRE (prossimo)
Obiettivo: portare il sistema a standard enterprise per deployment reale.
- **CI/CD pipelines**: GitHub Actions per build, test, lint e deploy automatico su push
- **Security hardening**: secrets rotation, network policies K8s, container scanning (Trivy)
- **SLO/SLA definition**: definire obiettivi di affidabilità misurabili (es. 99.5% uptime, p95 < 500ms)
- **Runbooks**: documentazione operativa per incident response e procedure di recovery
- **Chaos engineering**: fault injection controllata per validare resilience in produzione

> Tema chiave: *"Come garantisci affidabilità e sicurezza di un sistema AI in produzione?"*

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
