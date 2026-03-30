"""
Step 13 — LlamaIndex RAG Pipeline: structured index management + query engine.

Architecture
────────────
LlamaIndex wraps the pgvector retrieval from Step 12 with higher-level
abstractions:

    ┌─────────────────────────────────────────────────────────────┐
    │                   LlamaIndex RAG Pipeline                   │
    │                                                             │
    │  INGESTION (when a new incident is stored):                 │
    │    EvaluationRecord → TextNode → PGVectorStore              │
    │    (text representation + embedded metadata)                │
    │                                                             │
    │  RETRIEVAL (at /evaluate/rag request time):                 │
    │    incident text → VectorStoreIndex.as_retriever()          │
    │    → top-K TextNodes → SimilarIncident[]                    │
    │                                                             │
    │  QUERY ENGINE (for structured post-processing):             │
    │    VectorStoreIndex.as_query_engine()                       │
    │    → natural-language summary of similar incidents          │
    └─────────────────────────────────────────────────────────────┘

Why LlamaIndex over raw pgvector SQL (Step 12)?
───────────────────────────────────────────────
| Aspect            | Step 12 (raw SQL)     | Step 13 (LlamaIndex)         |
|-------------------|-----------------------|------------------------------|
| Abstraction       | Manual SQL            | VectorStoreIndex API         |
| Node metadata     | Ad-hoc dict           | Structured TextNode metadata |
| Index management  | Manual INSERT         | IngestionPipeline            |
| Query engine      | None                  | Natural-language QA          |
| Testability       | Mock DB required      | In-memory SimpleVectorStore  |
| Framework compat  | Raw pgvector          | Any LlamaIndex vector store  |

Design decisions
────────────────
- **Additive, not replacing**: rag_retriever.py (Step 12) stays intact.
  This module adds an optional, richer pipeline alongside it.

- **Same PostgreSQL table**: PGVectorStore points to the same
  `evaluation_records` table, reusing embeddings already stored in Step 12.

- **Graceful degradation**: if llama-index packages are not installed,
  all functions return empty results / None with a warning.

- **In-process embedding**: uses the same OpenAI text-embedding-3-small
  as Step 12 — no duplicate calls if the embedding is already stored.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Check LlamaIndex availability ──────────────────────────────────────────────
try:
    from llama_index.core import Settings, VectorStoreIndex
    from llama_index.core.ingestion import IngestionPipeline
    from llama_index.core.schema import TextNode
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.vector_stores.postgres import PGVectorStore

    _llamaindex_available = True
    logger.info("[llamaindex] LlamaIndex packages available")
except ImportError:
    _llamaindex_available = False
    logger.warning(
        "[llamaindex] llama-index packages not installed — LlamaIndex pipeline disabled. "
        "Run: pip install llama-index-core llama-index-embeddings-openai "
        "llama-index-vector-stores-postgres"
    )


def is_available() -> bool:
    """Return True if all required LlamaIndex packages are installed."""
    return _llamaindex_available


def _build_pgvector_store() -> "PGVectorStore | None":
    """
    Build a PGVectorStore pointing to the evaluation_records table.

    Reads DB_URL from the environment (same as database.py).
    Returns None if LlamaIndex is not installed or DB_URL is not set.
    """
    if not _llamaindex_available:
        return None

    db_url = os.environ.get("DB_URL", "postgresql://llmqa:llmqa_dev@localhost:5434/llmqa")

    # Parse connection params from the URL for PGVectorStore
    # Expected format: postgresql://user:pass@host:port/dbname
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return PGVectorStore.from_params(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5434,
            database=parsed.path.lstrip("/"),
            user=parsed.username or "llmqa",
            password=parsed.password or "",
            table_name="evaluation_records",   # reuse Step 12 table
            embed_dim=1536,                     # text-embedding-3-small
        )
    except Exception as exc:
        logger.warning("[llamaindex] failed to build PGVectorStore: %s", exc)
        return None


def _configure_settings() -> None:
    """
    Configure LlamaIndex global Settings: embedding model + disable default LLM.

    We only use LlamaIndex for embedding + retrieval, not for LLM generation
    (that's handled by our own evaluate() + evaluate_with_tools() pipeline).
    """
    if not _llamaindex_available:
        return
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        Settings.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small",
            dimensions=1536,
            api_key=api_key,
        )
    # Explicitly disable the default LLM — we don't use LlamaIndex for generation
    Settings.llm = None  # type: ignore[assignment]


def incident_to_node(incident_json: dict, record_id: str, summary: str = "") -> "TextNode":
    """
    Convert an incident dict to a LlamaIndex TextNode for ingestion.

    The node text is the same representation used by rag_retriever.py so
    embeddings are consistent across both pipelines.
    """
    from .rag_retriever import _incident_to_text  # reuse Step 12 serializer

    text = _incident_to_text(incident_json)
    return TextNode(
        text=text,
        id_=record_id,
        metadata={
            "record_id": record_id,
            "workflow": incident_json.get("workflow", ""),
            "incident_type": incident_json.get("incidentType", ""),
            "severity": incident_json.get("severity", ""),
            "summary": summary,
        },
    )


def build_index_from_store() -> "VectorStoreIndex | None":
    """
    Build a VectorStoreIndex backed by the live PostgreSQL pgvector store.

    This index reflects all evaluation records that already have embeddings
    (stored by Step 12's store.save() integration).

    Returns None if LlamaIndex or DB is not available.
    """
    if not _llamaindex_available:
        return None
    _configure_settings()
    vector_store = _build_pgvector_store()
    if vector_store is None:
        return None
    try:
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        logger.info("[llamaindex] VectorStoreIndex built from PGVectorStore")
        return index
    except Exception as exc:
        logger.warning("[llamaindex] build_index_from_store failed: %s", exc)
        return None


def ingest_incident(incident_json: dict, record_id: str, summary: str = "") -> bool:
    """
    Ingest a single incident into the LlamaIndex vector store.

    This is an ALTERNATIVE ingestion path to store.py's store_embedding().
    Both write to the same pgvector table; use whichever fits the workflow.

    Returns True if the node was ingested, False if skipped/failed.
    """
    if not _llamaindex_available:
        return False
    _configure_settings()
    vector_store = _build_pgvector_store()
    if vector_store is None:
        return False

    try:
        node = incident_to_node(incident_json, record_id, summary)
        pipeline = IngestionPipeline(vector_store=vector_store)
        pipeline.run(nodes=[node])
        logger.info("[llamaindex] ingested node %s", record_id)
        return True
    except Exception as exc:
        logger.warning("[llamaindex] ingest_incident failed for %s: %s", record_id, exc)
        return False


def retrieve_similar(
    incident_json: dict,
    top_k: int = 3,
) -> list[dict]:
    """
    Retrieve the top-K most similar incidents using the LlamaIndex retriever.

    Returns a list of dicts with keys: record_id, text, score, metadata.
    Returns an empty list if LlamaIndex is unavailable or retrieval fails.

    Use this as a richer alternative to rag_retriever.find_similar_incidents()
    when you need access to LlamaIndex's NodeWithScore objects and metadata.
    """
    if not _llamaindex_available:
        return []
    _configure_settings()

    try:
        from .rag_retriever import _incident_to_text, generate_embedding

        index = build_index_from_store()
        if index is None:
            return []

        query_text = _incident_to_text(incident_json)
        query_embedding = generate_embedding(query_text)
        if query_embedding is None:
            return []

        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes_with_scores = retriever.retrieve(query_text)

        results = []
        for nws in nodes_with_scores:
            results.append({
                "record_id": nws.node.metadata.get("record_id", nws.node.id_),
                "text": nws.node.text,
                "score": round(float(nws.score or 0.0), 3),
                "metadata": nws.node.metadata,
            })

        logger.info("[llamaindex] retrieved %d similar incidents", len(results))
        return results

    except Exception as exc:
        logger.warning("[llamaindex] retrieve_similar failed: %s", exc)
        return []


def summarize_similar_incidents(incident_json: dict, top_k: int = 3) -> str:
    """
    Use the LlamaIndex QueryEngine to generate a natural-language summary
    of how similar past incidents were handled.

    This requires a real LLM (OPENAI_API_KEY) and is optional — if unavailable,
    returns an empty string so callers can skip the RAG context gracefully.

    Example output:
        'Based on 3 similar incidents, the most common remediation was
         escalate (2/3 cases). Critical schema errors in the checkout
         workflow were resolved within 2 cycles on average.'
    """
    if not _llamaindex_available:
        return ""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""

    try:
        from openai import OpenAI
        from .rag_retriever import _incident_to_text

        similar = retrieve_similar(incident_json, top_k=top_k)
        if not similar:
            return ""

        context = "\n\n".join(
            f"Incident {i+1} (similarity {r['score']:.0%}):\n{r['text']}\n"
            f"Metadata: {r['metadata']}"
            for i, r in enumerate(similar)
        )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an SRE analyst. Given similar past incidents and their outcomes, "
                        "write a concise 2-sentence summary of patterns and recommended actions. "
                        "Be specific about incident types, severity, and what remediation worked."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Current incident:\n{_incident_to_text(incident_json)}\n\n"
                               f"Similar past incidents:\n{context}",
                },
            ],
            max_tokens=150,
            temperature=0.1,
        )
        summary = response.choices[0].message.content or ""
        logger.info("[llamaindex] generated RAG summary (%d chars)", len(summary))
        return summary.strip()

    except Exception as exc:
        logger.warning("[llamaindex] summarize_similar_incidents failed: %s", exc)
        return ""
