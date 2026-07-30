"""
Search & Chat routes — semantic search and conversational RAG.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from collections import defaultdict

from auth.jwt_handler import get_current_user
from database.db import get_db
from database.models import AuditLog, Document, User
from middleware.security import check_rate_limit
from services.retriever import rag_answer

router = APIRouter(prefix="/api", tags=["Search & Chat"])

# In-memory chat history per session (user_id -> list of messages)
# In production, persist this to DB
_chat_histories: dict = defaultdict(list)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=100)


@router.post("/search")
def semantic_search(
    req: SearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Semantic search + RAG answer over the authenticated user's documents.
    Returns matching document metadata + a synthesized AI answer.
    """
    check_rate_limit(request, "search")

    try:
        result = rag_answer(user_id=current_user.id, query=req.query)
    except Exception as e:
        print(f"[Search] RAG error: {type(e).__name__}: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    # Enrich sources with full DB metadata (ownership already guaranteed by user_id scope)
    enriched_sources = []
    for src in result["sources"]:
        doc = db.query(Document).filter(
            Document.id == src["doc_id"],
            Document.user_id == current_user.id,  # Double-check ownership
        ).first()
        if doc:
            enriched_sources.append({
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "organization": doc.organization,
                "date": doc.doc_date,
                "skills": doc.skills or [],
                "score": src["score"],
            })

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="search",
        detail=req.query[:200],
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return {"answer": result["answer"], "sources": enriched_sources}


@router.post("/chat")
def chat(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Conversational RAG chat — maintains per-session history for context.
    All context is drawn only from the user's own documents.
    """
    check_rate_limit(request, "search")

    session_key = f"{current_user.id}:{req.session_id or 'default'}"
    history = _chat_histories[session_key]

    try:
        result = rag_answer(
            user_id=current_user.id,
            query=req.message,
            chat_history=history,
        )
    except Exception as e:
        print(f"[Chat] RAG error: {type(e).__name__}: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    # Update history
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["answer"]})

    # Keep only last 10 turns to prevent memory bloat
    if len(history) > 20:
        _chat_histories[session_key] = history[-20:]

    return {
        "reply": result["answer"],
        "sources": result["sources"],
        "session_id": req.session_id or "default",
    }
