"""
Seed the HELIOS knowledge base into ChromaDB.
Run this once before starting the server:

    python scripts/seed_knowledge_base.py

This populates Foundry IQ (ChromaDB) with all documents from /knowledge-base/.
Documents are chunked, embedded with sentence-transformers, and indexed.
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge-base"
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 100


def chunk_document(text: str, filename: str, metadata: dict) -> list[dict]:
    """Split a document into overlapping chunks."""
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        chunks.append({
            "text": chunk_text,
            "metadata": {**metadata, "chunk_idx": chunk_idx},
            "id": f"{filename}::chunk{chunk_idx}"
        })
        start += CHUNK_SIZE - CHUNK_OVERLAP
        chunk_idx += 1
    return chunks


def classify_source_type(path: Path) -> str:
    """Classify document source type from path."""
    parts = str(path).lower()
    if "incident" in parts or "postmortem" in parts:
        return "incident_postmortem"
    elif "advisor" in parts:
        return "vendor_advisory"
    elif "runbook" in parts:
        return "runbook"
    elif "standard" in parts or "guideline" in parts:
        return "config_standard"
    else:
        return "industry_postmortem"


def extract_metadata(text: str, path: Path) -> dict:
    """Extract metadata from document front matter."""
    metadata = {}
    lines = text.split("\n")

    for line in lines[:10]:
        if "**Date:**" in line or "**Incident Date:**" in line:
            metadata["date"] = line.split("**Date:**")[-1].strip().lstrip("*").strip()
        if "INC-" in text[:200]:
            import re
            match = re.search(r"INC-\d+", text[:200])
            if match:
                metadata["incident_id"] = match.group()
        if "**Revenue Impact:**" in line or "Revenue Impact:" in line:
            metadata["revenue_impact_raw"] = line.split(":")[-1].strip()

    # Try to extract outcome from first paragraph
    paragraphs = text.split("\n\n")
    if paragraphs:
        metadata["outcome"] = paragraphs[1][:200] if len(paragraphs) > 1 else ""

    return metadata


def seed():
    """Main seeding function."""
    import chromadb
    from sentence_transformers import SentenceTransformer
    import os

    logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Init ChromaDB
    use_local = os.getenv("CHROMA_LOCAL", "true").lower() == "true"
    if use_local:
        data_path = Path(__file__).parent.parent / ".chroma_data"
        data_path.mkdir(exist_ok=True)
        client = chromadb.PersistentClient(path=str(data_path))
        logger.info(f"ChromaDB: local at {data_path}")
    else:
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8001"))
        client = chromadb.HttpClient(host=host, port=port)
        logger.info(f"ChromaDB: remote at {host}:{port}")

    collection_name = os.getenv("CHROMA_COLLECTION", "helios_knowledge_base")

    # Delete existing collection to re-seed
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted existing collection '{collection_name}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    logger.info(f"Created collection '{collection_name}'")

    # Walk knowledge base
    all_docs = list(KNOWLEDGE_BASE_PATH.rglob("*.md"))
    logger.info(f"Found {len(all_docs)} documents in knowledge base")

    all_chunks = []
    for doc_path in all_docs:
        text = doc_path.read_text(encoding="utf-8")
        source_type = classify_source_type(doc_path)
        extra_meta = extract_metadata(text, doc_path)

        # Extract title from first line
        title = ""
        for line in text.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        metadata = {
            "source_doc": doc_path.name,
            "source_type": source_type,
            "title": title,
            "relative_path": str(doc_path.relative_to(KNOWLEDGE_BASE_PATH)),
            **extra_meta,
        }

        chunks = chunk_document(text, doc_path.stem, metadata)
        all_chunks.extend(chunks)
        logger.info(f"  {doc_path.name}: {len(chunks)} chunks, type={source_type}")

    logger.info(f"Total chunks to embed: {len(all_chunks)}")

    # Embed in batches
    BATCH_SIZE = 32
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"  Indexed batch {i // BATCH_SIZE + 1}/{(len(all_chunks) + BATCH_SIZE - 1) // BATCH_SIZE}")

    final_count = collection.count()
    logger.info(f"✅ Knowledge base seeded: {final_count} chunks indexed in '{collection_name}'")
    logger.info(f"   Documents: {len(all_docs)}")
    logger.info(f"   Chunks: {final_count}")
    logger.info(f"   Embedding model: all-MiniLM-L6-v2")
    logger.info("\nFoundry IQ is ready. Start HELIOS server: uvicorn api.server:app --reload")


if __name__ == "__main__":
    seed()
