"""
RAG retrieval service — combines ChromaDB semantic search with Gemini Flash
to answer natural language queries about user documents.
"""
import os
from typing import List, Dict
import google.generativeai as genai
from services.embedder import query_documents

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

CANDIDATE_MODELS = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

SYSTEM_PROMPT = """You are MemoryVerse AI, an intelligent personal assistant helping a student
find and understand their own academic and professional documents.

Answer the user's question using ONLY the provided context from their documents.
If the context doesn't contain the answer, say so honestly — do not make things up.
Be concise, helpful, and specific — mention actual document titles, organizations, and dates when relevant.
Format your answer in plain readable text."""


def _generate_with_fallback(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not configured in Vercel settings.")
    genai.configure(api_key=api_key)

    last_err = None
    for m in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(
                model_name=m,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1000,
                ),
            )
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            last_err = e
            print(f"[Retriever] Model {m} failed: {e}")
            continue
    raise RuntimeError(f"All Gemini models failed: {last_err}")


def rag_answer(user_id: int, query: str, chat_history: List[Dict] = None) -> Dict:
    """
    Retrieval-Augmented Generation pipeline using Gemini:
    1. Semantic search with Gemini embeddings
    2. Build context from top results
    3. Gemini synthesizes a natural language answer
    """
    results = query_documents(user_id=user_id, query_text=query, top_k=5)

    if not results:
        return {
            "answer": "I couldn't find any documents related to your query. Try uploading some documents first!",
            "sources": []
        }

    context_parts = []
    sources = []
    for r in results:
        meta = r["metadata"]
        snippet = r.get("text_snippet") or meta.get("title", "")
        context_parts.append(
            f"[{meta.get('category', 'Document')}] \"{meta.get('title', 'Untitled')}\"\n{snippet}"
        )
        sources.append({
            "doc_id": r["doc_id"],
            "title": meta.get("title", "Untitled"),
            "category": meta.get("category", ""),
            "score": round(r["score"], 3),
        })

    context = "\n\n---\n\n".join(context_parts)

    conversation_parts = [SYSTEM_PROMPT]

    if chat_history:
        for msg in chat_history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_parts.append(f"{role}: {msg['content']}")

    conversation_parts.append(
        f"Context from the user's documents:\n\n{context}\n\nUser question: {query}"
    )

    full_prompt = "\n\n".join(conversation_parts)

    print(f"[Retriever] Sending query to Gemini: '{query[:80]}'")
    answer = _generate_with_fallback(full_prompt)
    print(f"[Retriever] Answer generated ({len(answer)} chars)")

    return {"answer": answer, "sources": sources}
