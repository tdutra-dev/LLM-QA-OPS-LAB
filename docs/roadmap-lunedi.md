# Roadmap Lunedì — Nuovo PC
> Creato: April 17, 2026
> Sessione: primo giorno sul nuovo PC

---

## 0. Prima cosa assoluta — fix Docker (10 min)

```bash
sudo usermod -aG docker $USER
# logout completo + login
# verifica:
docker ps
docker compose up --build -d   # nel progetto llm-qa-ops-lab
```
Senza questo i container vengono avviati da root e diventano irremovibili.
(Problema confermato Apr 16 — grafana e dash-app bloccati, serve riavvio).

---

## 1. Setup nuovo PC — verificare che tutto funzioni (30 min)

- [ ] Clonare / copiare il repo llm-qa-ops-lab
- [ ] `docker compose up --build -d` — tutti i servizi up
- [ ] `http://localhost:8010/docs` — FastAPI risponde
- [ ] `http://localhost:3000` — Grafana con metriche live
- [ ] `cd packages/eval-py && source .venv/bin/activate && pytest tests/ -v` — 278 green
- [ ] Aprire il workspace in VS Code, verificare che Copilot chat carichi il contesto

---

## 2. Job search — azioni concrete (priorità alta)

### 2a. README visual-finetune-lab (2-3h)
**Obiettivo:** trasformare il repo in una landing page tecnica che si vende da sola.

Struttura:
```
1. Badge + headline: "End-to-End Vision Model Specialization — ~10x cost reduction vs GPT-4o"
2. "The Problem" — labeling manuale costoso, dipendenza GPT-4o a runtime
3. Diagramma pipeline: OpenCV → GPT-4o dataset gen → QLoRA → FastAPI
4. Metriche: BLEU/ROUGE-L, costo per inference, tempo training
5. Screenshot: MLflow run, output JSON API, esempio input/output
6. Stack badges
7. Quick start Docker
```
→ Risultato: secondo progetto AI pronto per essere linkato nel CV e nell'outreach

### 2b. Profilo Wellfound (1h)
**Obiettivo:** profilo completo, pronto per essere trovato dai founder.

Checklist:
- [ ] Foto professionale
- [ ] Headline: "AI Backend Engineer · Python · LLMOps · Production AI Systems"
- [ ] Bio: 3-4 righe, stesso tono del CV
- [ ] Sezione Projects: LLM-QA-OPS-LAB + visual-finetune-lab con link GitHub
- [ ] Stack selezionato: Python, FastAPI, LangGraph, pgvector, RAG, OpenAI, LLMOps
- [ ] Disponibilità: Full-Remote, open a full-time + freelance
- [ ] Salary expectation: da decidere (metti un range realistico)

### 2c. Lista target companies (1h)
**Obiettivo:** 10-20 aziende concrete, no agenzie.

Criteri di selezione:
- Usano Python + AI/LLM in produzione
- Remote-friendly
- Hanno un engineering team visibile su GitHub o blog tecnico
- Cercano AI/Backend o hanno JD pubbliche in quella direzione

Dove cercare:
- Wellfound — filtra per AI/ML + remote + size 10-200
- Otta.com — filtra per "AI Engineer" o "Backend Python"
- YC companies (ycombinator.com/companies) — filtra AI + hiring
- LinkedIn top voices AI Italy → guarda dove lavorano

Formato output (salva qui sotto o in un file separato):
```
| Azienda | Sito | Fit | Note |
```

### 2d. Template outreach (30 min)
**Obiettivo:** un template riusabile per contattare CTO/EM direttamente.

Struttura del messaggio (LinkedIn DM o email):
```
Ciao [Nome],

Ho visto che [azienda] sta [costruendo X / cercando Y].

Ho appena finito [LLM-QA-OPS-LAB] — un AIOps layer in Python che fa 
ingestion universale, batch LLM analysis e faithfulness evaluation con 
Prometheus/Grafana. [link GitHub]

Stai cercando qualcuno con questo background? Sono aperta a una 
conversazione informale.

Tendresse
```
→ 3-4 varianti: per founder, per CTO tecnico, per EM, per remote-first startup

---

## 3. Tecnico — opzionale (solo se time allows)

Questi non sono urgenti, ma se lunedì avanzasse tempo:

### 3a. Dashboard Grafana dedicata LLM evaluation metrics
Creare un secondo pannello Grafana con i 4 metric specifici delle fasi:
- `hallucination_risk` distribution
- `confidence_score` distribution
- `rag_faithfulness_score` distribution
- `faithfulness_total` per verdict (faithful / partial / hallucinated)

### 3b. Workflow automatico faithfulness post-batch
Dopo ogni `/batch/analyze`, chiamare automaticamente `/batch/faithfulness`
e salvare il risultato su PostgreSQL — closing the loop senza intervento manuale.

---

## Priorità assoluta lunedì

```
1. Fix Docker (10 min) — sblocca tutto il resto
2. Verifica setup (30 min) — 278 test green, Grafana up
3. README visual-finetune-lab (2-3h) — secondo progetto nel CV/outreach
4. Profilo Wellfound (1h) — trovabile dai founder
5. Lista target companies (1h) — sapere a chi scrivere
6. Template outreach (30 min) — pronta per mandare messaggi
```

---

## Riferimenti utili

- Contesto completo: docs/context-nuovo-pc.md (questo progetto)
- Roadmap tecnica: docs/ROADMAP.md
- CV aggiornato: in memoria Copilot (career-plan.md)
- Repo llm-qa-ops-lab: github.com/tdutra-dev/LLM-QA-OPS-LAB
- Repo visual-finetune-lab: github.com/tdutra-dev/visual-finetune-lab
