"""
Foundry IQ Integration — HELIOS
Enterprise knowledge retrieval powered by ChromaDB vector database populated with real knowledge base documents.
Interface matches Foundry IQ's grounded retrieval API surface exactly.
To swap for real Foundry IQ: replace the `search()` implementation only.
"""
from __future__ import annotations
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import to avoid slow startup when not needed
_client = None
_collection = None


def _get_client():
    """Initialize ChromaDB client (singleton)."""
    global _client
    if _client is None:
        import chromadb
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8001"))
        use_local = os.getenv("CHROMA_LOCAL", "true").lower() == "true"

        if use_local:
            # Persistent local client — no Docker needed for dev
            data_path = Path(__file__).parent.parent / ".chroma_data"
            data_path.mkdir(exist_ok=True)
            _client = chromadb.PersistentClient(path=str(data_path))
            logger.info(f"ChromaDB: local persistent at {data_path}")
        else:
            _client = chromadb.HttpClient(host=host, port=port)
            logger.info(f"ChromaDB: remote at {host}:{port}")
    return _client


def _get_collection():
    """Get or create the HELIOS knowledge base collection."""
    global _collection
    if _collection is None:
        client = _get_client()
        collection_name = os.getenv("CHROMA_COLLECTION", "helios_knowledge_base")
        try:
            _collection = client.get_collection(collection_name)
            logger.info(f"ChromaDB: loaded existing collection '{collection_name}' ({_collection.count()} docs)")
        except Exception:
            _collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.warning(f"ChromaDB: created new empty collection '{collection_name}' — run seed_knowledge_base.py")
    return _collection


def search(query: str, top_k: int = 5, source_type_filter: Optional[str] = None) -> list[dict]:
    """
    Semantic search over the HELIOS knowledge base.

    This is the Foundry IQ equivalent — grounded retrieval with citations.
    Returns a list of dicts matching the EvidenceItem schema.

    Args:
        query: Natural language search query
        top_k: Number of results to return
        source_type_filter: Optional filter by source type (e.g., 'incident_postmortem')

    Returns:
        List of dicts with keys: source_doc, source_type, title, relevant_excerpt, similarity_score
    """
    try:
        collection = _get_collection()

        if collection.count() == 0:
            logger.warning("Knowledge base is empty. Run: python scripts/seed_knowledge_base.py")
            return _fallback_evidence(query)

        where_filter = None
        if source_type_filter:
            where_filter = {"source_type": {"$eq": source_type_filter}}

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        evidence = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                # ChromaDB returns cosine distance (0=identical, 2=opposite)
                # Convert to similarity score (1=identical, 0=no match)
                similarity = max(0.0, 1.0 - (distance / 2.0))

                evidence.append({
                    "source_doc": meta.get("source_doc", "Unknown"),
                    "source_type": meta.get("source_type", "unknown"),
                    "title": meta.get("title", ""),
                    "relevant_excerpt": doc[:800],  # Cap at 800 chars for context window
                    "similarity_score": round(similarity, 3),
                    "incident_id": meta.get("incident_id"),
                    "date": meta.get("date"),
                    "outcome": meta.get("outcome"),
                    "revenue_impact": meta.get("revenue_impact"),
                })

        logger.info(f"Foundry IQ search '{query[:50]}...' → {len(evidence)} results")
        return evidence

    except Exception as e:
        logger.error(f"Foundry IQ search error: {e}")
        return _fallback_evidence(query)


def _fallback_evidence(query: str) -> list[dict]:
    """
    Fallback when ChromaDB is unavailable.
    Returns structured empty result — never hallucinated data.
    """
    logger.warning("Using fallback evidence (no ChromaDB). Install ChromaDB and seed the knowledge base.")
    return []


def collection_stats() -> dict:
    """Return stats about the knowledge base collection."""
    try:
        collection = _get_collection()
        return {
            "document_count": collection.count(),
            "collection_name": collection.name,
            "status": "ready" if collection.count() > 0 else "empty"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
