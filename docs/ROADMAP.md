# ROADMAP — Tendresse Dutra
> Ultimo aggiornamento: April 1, 2026
> Scopo: tracciare obiettivi, percorso tecnico e stato del progetto.
> **Questo file è il punto di partenza per qualsiasi nuova sessione di lavoro.**

---

## Chi è Tendresse

Backend Engineer con esperienza reale in sistemi distribuiti (Java Spring Boot, Kafka, MySQL,
Elasticsearch) maturata in un contesto e-commerce (SWAG). Conosce i concetti di observability
(log tracing con Elasticsearch), REST APIs, event-driven architecture.

Adesso: freelance, in ricerca di lavoro, vuole diventare AI/Backend Engineer con focus LLMOps.

---

## I due obiettivi — non sono in conflitto

```
OBIETTIVO 1 — trovare lavoro come AI Integration / Backend Engineer Python
OBIETTIVO 2 — costruire un prodotto proprio (AIOps intelligence layer)

→ Il prodotto È il percorso di apprendimento.
  Costruendo il prodotto si imparano esattamente le competenze richieste nelle interview.
```

---

## Il progetto esistente — LLM-QA-OPS-LAB

### Cosa fa adesso (stato attuale)
Un microservizio FastAPI che riceve incident da una pipeline LLM, li valuta con tre
strategie (regole deterministiche, OpenAI function calling, RAG su storico con pgvector),
e può reagire autonomamente tramite un agent LangGraph.

```
POST /evaluate          → rule-based (score, status, suggestedAction)
POST /evaluate/tool-call → OpenAI function calling
POST /evaluate/rag      → come sopra + cerca K casi simili nel DB (pgvector cosine)
POST /agent/start       → avvia LangGraph agent loop autonomo
GET  /prometheus-metrics → metriche per Grafana (9 custom metrics + SLO alerts)
```

**Stack**: Python 3.11 · FastAPI · SQLAlchemy · Pydantic V2 · PostgreSQL + pgvector ·
Redis · OpenAI API · LangGraph · LlamaIndex · Prometheus · Grafana · Docker · Kubernetes

**Database**: 4800+ record con embedding OpenAI già generati (text-embedding-3-small, 1536 dim)

**Problema noto**: pgvector extension non attiva nel container postgres (usa `postgres:16-alpine`
invece di `pgvector/pgvector:pg16`) → RAG hit rate = 0 in locale. I dati e la logica sono
corretti, manca solo l'estensione.

### Come difenderlo in interview
- "Perché RAG sugli incident?" → il contesto storico migliora la valutazione nel tempo (flywheel)
- "Perché LangGraph?" → grafo tipizzato, nodi testabili, routing condizionale, checkpointing
- "Cosa monitora Prometheus che non fa un APM?" → metriche di dominio: score distribution,
  RAG hit rate, azioni di remediation — non solo HTTP latency

### Cosa NON è (per non inciampare)
- Non monitora sistemi generici — solo incident nel suo formato specifico
- Le azioni autonome (restart/scale) sono pattern implementati, non integrate con K8s reale
- Non è un competitor di Datadog — è un quality gate per pipeline LLM

---

## La visione originale di Tendresse — il prodotto futuro

### Idea
Un **intelligence layer universale** che intercetta incident da qualsiasi sistema in produzione
(Spring Boot, Kafka, MySQL, Node, Python...) indipendentemente dal formato, li normalizza,
li accumula per finestra temporale, e li analizza in batch con un LLM — per dare
**awareness e qualità ai flussi di lavoro aziendali**.

### Architettura target
```
Qualsiasi sistema (Java, Node, Python, AWS...)
         ↓  HTTP o event-driven
  [INGESTION LAYER]
   POST /ingest/http-log
   POST /ingest/kafka-event
   POST /ingest/webhook
         ↓
  [NORMALIZATION LAYER]  ← il pezzo mancante e centrale
   ogni sorgente → IncidentEvent (formato universale)
         ↓
  [ACCUMULATOR — Redis Stream]
   buffer per finestra temporale (es. 5 minuti)
   raggruppa per: service, severity, tipo errore
         ↓  (batch job ogni N minuti)
  [LLM ANALYSIS ENGINE — 1 chiamata per batch, non per evento]
   "hai questi 47 eventi negli ultimi 5 min, cosa sta succedendo?"
         ↓
  [OUTPUT LAYER]
   Incident report strutturato
   Prometheus counter (classificazione)
   Slack / Jira / email
```

### Perché ha senso commerciale
- Categoria: **AIOps** — mercato da miliardi, player esistenti (BigPanda, Moogsoft) sono
  proprietari, costosi, senza LLM nativo
- Il batch approach risolve il problema reale: un LLM che legge 50 eventi insieme
  vede il pattern; uno che legge 1 evento alla volta è cieco e costoso
- La normalization layer risolve il problema reale nelle aziende: 15 sistemi che
  emettono eventi in 15 formati diversi

### Componenti del progetto esistente riusabili
- FastAPI → receiver degli eventi normalizzati
- Redis → accumulator (stream/buffer)
- PostgreSQL → storico incident normalizzati
- OpenAI function calling → analysis engine batch
- Prometheus + Grafana → awareness dashboard
- LangGraph → workflow di analisi

### Cosa manca da costruire
1. `IncidentEvent` — modello universale normalizzato (Fase 1)
2. Normalizer per ogni sorgente: SpringBootNormalizer, KafkaNormalizer, WebhookNormalizer
3. Ingestion endpoints multipli (`/ingest/*`)
4. Batch analyzer (Redis Stream → finestra temporale → 1 chiamata OpenAI)
5. RAG su storico incident normalizzati

---

## Percorso di apprendimento — 4 fasi

### FASE 1 — Python Expert (3-4 settimane) ← INIZIAMO DA QUI
**Competenza target**: Python tipizzato, Pydantic V2, pytest, async

**Cosa costruiamo**: il modello `IncidentEvent` — cuore del prodotto
```python
class IncidentEvent(BaseModel):
    source_system: Literal["spring-boot", "kafka", "mysql", "generic"]
    severity: SeverityLevel       # Enum tipizzato
    service: str
    message: str
    timestamp: datetime
    raw: dict[str, Any]
    error_type: str | None = None
    affected_resource: str | None = None
```
Con: validators, serializers, test completi, type safety end-to-end.

**Risorse** (tutte free):
- docs.pydantic.dev — validators, serializers, generics
- pytest docs — fixtures, parametrize, mock
- Python `typing` module — TypeVar, Generic, Protocol, Literal
- asyncio basics

**Checkpoint interview**: "Differenza Pydantic V1 vs V2 · model_validator vs field_validator
· TypedDict vs dataclass · perché Literal invece di str"

---

### FASE 2 — FastAPI avanzato + Ingestion Layer (2-3 settimane)
**Competenza target**: FastAPI avanzato, dependency injection, middleware, testing API

**Cosa costruiamo**: endpoint `/ingest/*` con normalizer pluggabile
```
POST /ingest/http-log     ← SpringBootNormalizer
POST /ingest/kafka-event  ← KafkaNormalizer
POST /ingest/webhook      ← WebhookNormalizer (GitHub, PagerDuty, qualsiasi)
```
Pattern: Strategy pattern per i normalizer — ogni sorgente è un plugin.

**Checkpoint interview**: "Middleware di autenticazione in FastAPI · testing con
dipendenze mockate · dependency injection vs global state · BackgroundTasks vs
Celery — quando scegli cosa"

---

### FASE 3 — Redis Streams + Batch LLM Analysis (3 settimane)
**Competenza target**: Redis avanzato, batch processing, OpenAI prompt engineering

**Cosa costruiamo**: il cuore del prodotto
- Redis Stream come buffer degli incident normalizzati
- Batch job ogni 5 minuti: leggi tutti gli eventi, costruisci prompt contestuale,
  chiama OpenAI una volta sola, salva l'analysis strutturata

**Checkpoint interview**: "Redis Streams vs Pub/Sub vs List · consumer group e
at-least-once delivery · come costruisci un prompt per analisi batch · structured
output con OpenAI response_format"

---

### FASE 4 — RAG su storico incident (2-3 settimane)
**Competenza target**: embeddings, pgvector, similarity search, LlamaIndex

**Cosa costruiamo**: quando arriva un batch di incident, cerca nel DB se la stessa
combinazione è già successa e cosa fu fatto — il sistema impara nel tempo.

Fix contestuale: attivare pgvector nel container (cambiare immagine docker-compose
da `postgres:16-alpine` a `pgvector/pgvector:pg16` + migrare colonna embedding
da text a vector(1536)).

**Checkpoint interview**: "Cosine similarity vs dot product · perché 1536 dimensioni ·
HNSW vs IVFFlat index · quando usi LlamaIndex vs pgvector diretto"

---

## Job offer target

### Ruolo obiettivo
**AI Integration Engineer / Backend Engineer AI focus / LLMOps Engineer**
Livello: Mid-level · Startup/scale-up · Remote Italy/EMEA

### Keyword LinkedIn da usare
```
"AI Integration Engineer Python Italy remote"
"LLMOps Engineer"
"Backend Engineer Python AI"
"AI Platform Engineer"
"GenAI Backend Engineer"
```

### Offerte analizzate (Aprile 2026)
| Offerta | Fit attuale | Note |
|---|---|---|
| Trimble — Agentic AI Engineer | ⭐ target a 4 mesi | Esattamente la direzione giusta |
| Pragmatik — AI Engineer Tech Lead | ❌ direzione sbagliata | Graph algorithms, non nel tuo stack |
| Deel — Senior Backend Engineer AI | ❌ over-leveled | 8+ anni, Node.js primary |
| S2E — Grafana Specialist | ⚠️ fallback freelance | Zero AI, direzione laterale |

---

## Stato sessioni di lavoro

| Data | Argomento | Risultato |
|---|---|---|
| Mar 31 – Apr 1, 2026 | Setup infrastruttura locale | eval-py su porta 8011, Prometheus UP, Grafana con dati live |
| Apr 1, 2026 | Analisi architettura e career path | Visione AIOps chiarita, percorso 4 fasi definito |
| Apr 1, 2026 (questa) | Struttura roadmap | Questo file |

---

## Note per future sessioni

**Per riprendere il lavoro**: leggi questo file per intero, poi chiedi a Tendresse
in quale fase si trova e cosa ha già fatto dell'ultima sessione.

**Prossima azione concreta**: iniziare Fase 1 — creare
`packages/eval-py/src/eval_py/incident_event.py` con il modello `IncidentEvent`
completo di typing, validators, e test in `tests/test_incident_event.py`.

**Regola di lavoro**: ogni sessione produce codice reale nel progetto, non
tutorial usa-e-getta. La spiegazione del perché viene sempre insieme al codice.
