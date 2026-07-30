"""
ChromaDB vector store service — manages per-user document collections
with Google Gemini embeddings for semantic search.
"""
import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

# ─── CLIENTS ──────────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_chroma_client: Optional[chromadb.Client] = None

# Gemini embedding model candidates (ordered by preference)
# text-embedding-004 is only available on v1 API, not v1beta used by the SDK
EMBED_MODELS = [
    "models/gemini-embedding-001",   # Newest — 3072-dim, best quality
    "models/embedding-001",          # Legacy stable fallback
]
default_chroma_dir = "/tmp/chroma_db" if os.getenv("VERCEL") else "./chroma_db"
CHROMA_DIR = os.getenv("CHROMA_DIR", default_chroma_dir)


def _get_chroma() -> chromadb.Client:
    """Lazy-initialize the persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def _user_collection(user_id: int) -> chromadb.Collection:
    """Each user gets their own isolated ChromaDB collection."""
    client = _get_chroma()
    return client.get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"},
    )


# ─── PUBLIC API ───────────────────────────────────────────────────────────────
def embed_text(text: str, task_type: str = "retrieval_document") -> List[float]:
    """
    Generate a Gemini embedding vector for the given text.
    task_type: "retrieval_document" for storing, "retrieval_query" for searching.
    """
    text = text[:8000]  # Stay within token limits
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
    raise RuntimeError(f"Embedding generation failed across all models: {last_err}")


def add_document(user_id: int, doc_id: int, text: str, metadata: Dict[str, Any]):
    """
    Add a document to the user's vector store.
    Each user has an isolated ChromaDB collection — no cross-user data access.
    """
    if not text or len(text.strip()) < 10:
        return  # Nothing to embed

    collection = _user_collection(user_id)
    embedding = embed_text(text, task_type="retrieval_document")

    # ChromaDB metadata values must be str/int/float/bool
    safe_meta = {
        "doc_id": doc_id,
        "category": str(metadata.get("category", "")),
        "title": str(metadata.get("title", "")),
        "organization": str(metadata.get("organization") or ""),
        "date": str(metadata.get("date") or ""),
    }

    collection.upsert(
        ids=[str(doc_id)],
        embeddings=[embedding],
        documents=[text[:2000]],   # Store first 2000 chars as context snippet
        metadatas=[safe_meta],
    )


def search_documents(user_id: int, query: str, n_results: int = 5) -> List[Dict]:
    """
    Semantic search within a user's document collection.
    Uses "retrieval_query" task type — optimized for Gemini's asymmetric retrieval.
    Returns list of {doc_id, score, text_snippet, metadata}.
    """
    collection = _user_collection(user_id)

    if collection.count() == 0:
        return []

    # Use retrieval_query task type for query embeddings (different from document embeddings)
    query_embedding = embed_text(query, task_type="retrieval_query")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i, doc_id_str in enumerate(results["ids"][0]):
        output.append({
            "doc_id": int(doc_id_str),
            "score": 1 - results["distances"][0][i],   # cosine similarity
            "text_snippet": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
        })
    return output


def delete_document(user_id: int, doc_id: int):
    """Remove a document embedding from the user's isolated collection."""
    try:
        collection = _user_collection(user_id)
        collection.delete(ids=[str(doc_id)])
    except Exception as e:
        print(f"[Embedder] Failed to delete doc {doc_id}: {e}")
