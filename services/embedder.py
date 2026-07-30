"""
Vector store service — manages document vector embeddings with Google Gemini
and cosine similarity search (supports pure Python/SQLite & ChromaDB fallback).
"""
import math
import os
from typing import List, Dict, Any, Optional
import google.generativeai as genai

# Try loading chromadb if installed
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    chromadb = None
    HAS_CHROMADB = False

# ─── CLIENTS ──────────────────────────────────────────────────────────────────
EMBED_MODELS = [
    "models/text-embedding-004",
    "text-embedding-004",
]
default_chroma_dir = "/tmp/chroma_db" if os.getenv("VERCEL") else "./chroma_db"
CHROMA_DIR = os.getenv("CHROMA_DIR", default_chroma_dir)


def _get_chroma():
    """Lazy-initialize ChromaDB client if available."""
    global _chroma_client
    if not HAS_CHROMADB:
        return None
    if _chroma_client is None:
        try:
            _chroma_client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
        except Exception as e:
            print(f"[Embedder] ChromaDB init error: {e}")
            _chroma_client = None
    return _chroma_client


def _user_collection(user_id: int):
    client = _get_chroma()
    if not client:
        return None
    try:
        return client.get_or_create_collection(
            name=f"user_{user_id}",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        return None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two vector lists in pure Python."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── PUBLIC API ───────────────────────────────────────────────────────────────
def embed_text(text: str, task_type: str = "retrieval_document") -> List[float]:
    """Generate a Gemini embedding vector for the given text."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set on Vercel/server.")
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GEMINI_API_KEY"] = api_key
    genai.configure(api_key=api_key)

    text = text[:8000]
    last_err = None
    for model_name in EMBED_MODELS:
        try:
            result = genai.embed_content(
                model=model_name,
                content=text,
                task_type=task_type,
            )
            return result["embedding"]
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Embedding generation failed: {last_err}")


def add_document(user_id: int, doc_id: int, text: str, metadata: Dict[str, Any]) -> List[float]:
    """
    Generate document embedding and store in ChromaDB (if active) and return vector.
    """
    vector = embed_text(text, task_type="retrieval_document")
    coll = _user_collection(user_id)
    if coll:
        try:
            coll.add(
                ids=[str(doc_id)],
                embeddings=[vector],
                documents=[text[:1000]],
                metadatas=[{k: str(v) for k, v in metadata.items()}],
            )
        except Exception as e:
            print(f"[Embedder] ChromaDB add error (falling back to SQLite vector): {e}")
    return vector


def query_documents(user_id: int, query_text: str = None, top_k: int = 5, *, query: str = None, n_results: int = None, **kwargs) -> List[Dict[str, Any]]:
    """
    Semantic search: returns top_k matching document chunks.
    Attempts ChromaDB query first, falling back to pure Python SQLite vector similarity.
    Accepts both query_text= and query= for backward compatibility.
    """
    actual_query = query_text or query or ""
    actual_top_k = n_results or top_k or 5
    query_vector = embed_text(actual_query, task_type="retrieval_query")
    coll = _user_collection(user_id)

    if coll:
        try:
            results = coll.query(
                query_embeddings=[query_vector],
                n_results=actual_top_k,
            )
            hits = []
            if results and results.get("ids") and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    dist = results["distances"][0][i] if results.get("distances") else 0.0
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                    hits.append({
                        "doc_id": int(doc_id),
                        "score": round(1.0 - dist, 4),
                        "metadata": meta,
                    })
                return hits
        except Exception as e:
            print(f"[Embedder] ChromaDB query error: {e}")

    # Fallback: SQLite vector search
    from database.db import SessionLocal
    from database.models import Document

    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.user_id == user_id,
            Document.status == "ready",
            Document.embedding.isnot(None),
        ).all()

        scored = []
        for d in docs:
            if d.embedding:
                sim = cosine_similarity(query_vector, d.embedding)
                scored.append({
                    "doc_id": d.id,
                    "score": round(sim, 4),
                    "text_snippet": (d.extracted_text or "")[:500],
                    "metadata": {
                        "category": d.category or "Other",
                        "title": d.title or d.original_filename,
                        "organization": d.organization or "",
                        "date": d.doc_date or "",
                    },
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:actual_top_k]
    finally:
        db.close()


def delete_document(user_id: int, doc_id: int):
    """Remove a document from the vector store."""
    coll = _user_collection(user_id)
    if coll:
        try:
            coll.delete(ids=[str(doc_id)])
        except Exception:
            pass




