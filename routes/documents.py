"""
Documents CRUD routes — list, get, download original file, delete, reprocess.
All endpoints are scoped to the authenticated user.
"""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.jwt_handler import get_current_user
from database.db import get_db
from database.models import AuditLog, Document, Relationship, User
from services.embedder import delete_document, add_document
from services.categorizer import categorize_document
from services.extractor import extract_text

router = APIRouter(prefix="/api/documents", tags=["Documents"])
UPLOAD_BASE_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))



def _get_user_doc(doc_id: int, user_id: int, db: Session) -> Document:
    """Fetch a document, enforcing ownership. Raises 404 if not found/not owned."""
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == user_id,   # <-- critical ownership check
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("")
def list_documents(
    category: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents for the current user, optionally filtered by category."""
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if category:
        query = query.filter(Document.category == category)
    docs = query.order_by(Document.created_at.desc()).all()
    return [_doc_to_dict(d) for d in docs]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single document by ID. Requires ownership."""
    doc = _get_user_doc(doc_id, current_user.id, db)

    # Audit log view access
    db.add(AuditLog(
        user_id=current_user.id,
        action="view",
        resource_type="document",
        resource_id=doc_id,
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return _doc_to_dict(doc)


@router.get("/{doc_id}/file")
def download_document(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download the original file. Requires ownership.
    Files are served directly from the user's isolated upload directory.
    """
    doc = _get_user_doc(doc_id, current_user.id, db)
    file_path = Path(doc.file_path).resolve()
    user_upload_dir = (UPLOAD_BASE_DIR / str(current_user.id)).resolve()

    # Enforce path traversal guard: file must reside inside user's upload directory
    try:
        file_path.relative_to(user_upload_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    # Audit log download
    db.add(AuditLog(
        user_id=current_user.id,
        action="download",
        resource_type="document",
        resource_id=doc_id,
        detail=f"Downloaded: {doc.original_filename}",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return FileResponse(
        path=str(file_path),
        filename=doc.original_filename,
        media_type="application/octet-stream",
    )


@router.delete("/{doc_id}")
def delete_doc(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document and its embeddings. Requires ownership."""
    doc = _get_user_doc(doc_id, current_user.id, db)

    # Remove file from disk safely
    try:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"[Delete] File unlink warning: {e}")

    # Remove embedding from ChromaDB safely
    try:
        delete_document(user_id=current_user.id, doc_id=doc_id)
    except Exception as e:
        print(f"[Delete] Embedder deletion warning: {e}")

    # Remove relationships
    try:
        db.query(Relationship).filter(
            (Relationship.source_doc_id == doc_id) | (Relationship.target_doc_id == doc_id)
        ).delete(synchronize_session=False)
    except Exception as e:
        print(f"[Delete] Relationship deletion warning: {e}")

    # Audit log before deleting
    db.add(AuditLog(
        user_id=current_user.id,
        action="delete",
        resource_type="document",
        resource_id=doc_id,
        detail=f"Deleted: {doc.original_filename}",
        ip_address=request.client.host if request.client else None,
    ))

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted successfully", "id": doc_id}


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "category": doc.category,
        "title": doc.title,
        "summary": doc.summary,
        "skills": doc.skills or [],
        "date": doc.doc_date,
        "organization": doc.organization,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/reprocess-all", status_code=status.HTTP_200_OK)
def reprocess_all_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-run AI categorization + embedding on all documents that are
    still classified as 'Other' or titled 'Untitled Document'.
    Useful after fixing model issues without needing to re-upload files.
    """
    # Target docs that clearly failed AI processing
    docs = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == "ready",
    ).filter(
        (Document.category == "Other") |
        (Document.category == None) |
        (Document.title == "Untitled Document") |
        (Document.title == None)
    ).all()

    if not docs:
        return {"message": "All documents are already properly categorized.", "processed": 0}

    processed = 0
    failed = 0
    for doc in docs:
        try:
            # Re-extract text if we have it stored, otherwise read from disk
            text = doc.extracted_text or ""
            if not text and doc.file_path:
                text = extract_text(doc.file_path)
                doc.extracted_text = text[:5000]

            if not text or len(text.strip()) < 20:
                continue

            meta = categorize_document(text, filename=doc.original_filename)

            doc.category     = meta["category"]
            doc.title        = meta["title"]
            doc.summary      = meta["summary"]
            doc.skills       = meta["skills"]
            doc.doc_date     = meta["date"]
            doc.organization = meta["organization"]

            # Re-embed with updated metadata
            add_document(
                user_id=current_user.id,
                doc_id=doc.id,
                text=text,
                metadata=meta,
            )
            processed += 1
        except Exception as e:
            print(f"[Reprocess] Failed for doc {doc.id}: {e}")
            failed += 1

    db.commit()
    return {
        "message": f"Re-processed {processed} document(s). {failed} failed.",
        "processed": processed,
        "failed": failed,
    }
