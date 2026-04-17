# Context per nuovo PC — Tendresse Dutra
> Creato: April 17, 2026 — da portare sul nuovo PC lunedì

---

## Chi sei

**Tendresse Dutra** — AI Backend Engineer, donna, base in Italia.
- 10+ anni in sistemi distribuiti (Java Spring Boot, Kafka, MySQL, Elasticsearch, C#/.NET)
- Switch deliberato verso AI/Backend Engineering con focus LLMOps
- Lingue: Italiano (bilingue) · Inglese (professionale) · Portoghese (madrelingua)
- Contatti: linkedin.com/in/tendresse-dutra · github.com/tdutra-dev
- Ricerca: Full-Remote, open Italy/EMEA, open full-time e freelance

---

## Target professionale

**Ruolo cercato:** AI Integration Engineer / Backend Engineer AI / LLMOps Engineer
**Livello:** Mid-level · Startup/scale-up · Remote

### Canali da usare (NO agenzie)
- Wellfound (ex AngelList) — contatto diretto con founder
- Otta.com — trasparenza salari
- cord.co — diretto con hiring manager
- Himalayas.app — remote-first AI/ML friendly
- arc.dev, levels.fyi/jobs, remoteok.com

### Strategia outreach
- Trovare CTO / Head of Engineering su LinkedIn
- Mandare **valore** (link progetto funzionante), non CV a freddo
- Messaggio breve con: progetto + link GitHub + domanda concreta

---

## Stato progetti (Apr 17, 2026)

### LLM-QA-OPS-LAB — COMPLETO ✅
github.com/tdutra-dev/LLM-QA-OPS-LAB  
README live con screenshot Grafana reali, pushato Apr 16, 2026.

**Cosa fa:**
AIOps Intelligence Layer — ingestion universale (Spring Boot, Kafka, webhooks),
normalizzazione in IncidentEvent, buffer Redis Streams per finestra temporale,
batch LLM analysis (1 chiamata per window), evaluation faithfulness (rule-based + LLM judge),
RAG con pgvector + LlamaIndex, LangGraph StateGraph con routing condizionale e memory.

**Fasi completate (tutte e 4):**
- Fase 1: IncidentEvent model — Pydantic V2, validators, 56 test
- Fase 2: Ingestion layer — SpringBoot/Kafka/Webhook normalizers, Strategy pattern, 78 test
- Fase 3: Redis Streams + Batch LLM Analyzer — stream buffer, 1 call per window, 82 test
- Fase 4: RAG Faithfulness Evaluator — rule-based + LLM judge, Prometheus metrics, 62 test

**Totale: 278 test, tutti green.**

**Stack:** Python 3.12 · FastAPI · PostgreSQL + pgvector · Redis Streams · OpenAI GPT-4o-mini ·
LlamaIndex · LangGraph · Prometheus · Grafana · Docker · Kubernetes · TypeScript · GitHub Actions · Trivy

**Metriche Prometheus (13 custom):** hallucination rate, faithfulness score, RAG hit rate,
RAG latency, agent loop iterations, action executor, batch analysis totals.

**SLO alerts:** error rate < 1%, p95 latency /evaluate < 500ms, RAG hit rate > 60%.

**CI/CD:** GitHub Actions → ruff, pytest, eslint, vitest → docker build → GHCR push → Trivy CVE scan.

**API endpoints principali:**
- POST /ingest/http-log · /ingest/kafka-event · /ingest/webhook
- POST /batch/analyze · POST /batch/faithfulness · GET /stream/status
- POST /evaluate · /evaluate/tool-call · /evaluate/rag
- POST /agent/start · GET /agent/status
- GET /prometheus-metrics · /metrics · /health

**Servizi locali (docker compose up):**
- FastAPI + Swagger: http://localhost:8010/docs
- Dash dashboard: http://localhost:8050
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin / llmqa_dev)

---

### visual-finetune-lab — IN CORSO (README da fare) ⚠️
github.com/tdutra-dev/visual-finetune-lab

**Cosa fa:**
Pipeline E2E vision model — OpenCV preprocessing, GPT-4o dataset generation (20 Q&A pairs,
fattura PayPal reale), QLoRA Phi-3.5-Vision fine-tuning (~10x cost reduction design),
MLflow tracking su Databricks, FastAPI serving per Azure Container Apps.

**Stato:** full training pipeline implementata, checkpoint in progress su Colab T4.

**Stack:** Python · OpenCV · OpenAI API · HuggingFace PEFT · QLoRA · Phi-3.5-Vision · MLflow · Databricks · FastAPI · Docker · Azure Container Apps

**Prossima azione:** costruire il README come landing page tecnica (vedi piano sotto).

---

## Piano README visual-finetune-lab

Struttura da costruire nella prossima sessione:
1. Badge + headline: "End-to-End Vision Model Specialization — ~10x cost reduction vs GPT-4o at scale"
2. Sezione "The Problem": labeling manuale costoso, dipendenza da GPT-4o a runtime
3. Diagramma pipeline: OpenCV → GPT-4o dataset gen → QLoRA fine-tuning → FastAPI serving
4. Metriche concrete: BLEU/ROUGE-L prima/dopo, costo per inference, tempo training
5. Screenshot: MLflow run con metriche, output API JSON, esempio input/output
6. Stack badges visibili in cima
7. Quick start con Docker

---

## CV attuale (versione Apr 17, 2026) — VERIFICATO vs progetto

La descrizione di LLM-QA-OPS-LAB nel CV corrisponde esattamente allo stato reale.
Unico typo noto: "VVISUAL-FINETUNE-LAB" → "VISUAL-FINETUNE-LAB" (doppia V in una versione).

---

## Fix tecnici da fare al setup nuovo PC

### Fix Docker (priorità alta — prima cosa)
```bash
sudo usermod -aG docker $USER
# poi logout/login completo
```
Senza questo i container vengono avviati da root e non si possono fermare.
Fonte problema: Apr 16, grafana e dash-app irremovibili senza riavvio.

### Workflow standard progetto
```bash
cd /home/tendresse/projects/llm-qa-ops-lab
docker compose up --build -d         # avvia tutto
cd packages/eval-py
source .venv/bin/activate            # o ricrea se necessario
pytest tests/ -v                     # deve dare 278 green
```

---

## File chiave nel progetto

| File | Descrizione |
|------|-------------|
| docs/ROADMAP.md | Roadmap tecnica completa + storico sessioni |
| packages/eval-py/src/eval_py/incident_event.py | Fase 1 — IncidentEvent model |
| packages/eval-py/src/eval_py/normalizers.py | Fase 2 — SpringBoot/Kafka/Webhook normalizers |
| packages/eval-py/src/eval_py/stream_buffer.py | Fase 3 — Redis Stream buffer |
| packages/eval-py/src/eval_py/batch_analyzer.py | Fase 3 — Batch LLM analyzer |
| packages/eval-py/src/eval_py/rag_faithfulness.py | Fase 4 — Faithfulness evaluator |
| docker-compose.yml | Usa pgvector/pgvector:pg16 (fix Apr 13) |
| prometheus/alerts/slo.yml | SLO alert rules |
| prometheus/grafana/provisioning/ | Grafana auto-provisioning |

---

## Azioni prioritarie job search (in ordine, Apr 17)

1. [x] README LLM-QA-OPS-LAB — pushato Apr 16, 2026
2. [ ] README visual-finetune-lab — landing page tecnica
3. [ ] Profilo Wellfound aggiornato con entrambi i progetti
4. [ ] Lista 10-20 target companies concrete (no agenzie)
5. [ ] Template outreach personalizzabile per CTO/EM
6. [ ] Primo post tecnico su dev.to o LinkedIn

---

## Note operative

- Copilot agent sa tutto questo contesto già in memoria — basta riaprire il workspace
- Il file docs/ROADMAP.md è il punto di partenza per ogni nuova sessione tecnica
- Regola di lavoro: ogni sessione produce codice reale nel progetto, non tutorial usa-e-getta
