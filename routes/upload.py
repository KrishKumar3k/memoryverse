"""
File upload route — validates, extracts, categorizes, and embeds documents.
All files are stored in a user-specific isolated directory.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from auth.jwt_handler import get_current_user
from database.db import get_db
from database.models import AuditLog, Document, User
from middleware.security import check_rate_limit
from services.categorizer import categorize_document
from services.embedder import add_document
from services.extractor import extract_text

router = APIRouter(prefix="/api", tags=["Documents"])

# ─── SECURITY CONFIG ──────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
default_upload_dir = "/tmp/uploads" if os.getenv("VERCEL") else "uploads"
UPLOAD_BASE_DIR = Path(os.getenv("UPLOAD_DIR", default_upload_dir))


def _get_user_upload_dir(user_id: int) -> Path:
    """Returns (and creates) the user-specific upload directory."""
    user_dir = UPLOAD_BASE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _sanitize_filename(filename: str) -> str:
    """
    Use werkzeug's secure_filename to strip path traversal characters,
    then prefix with a UUID to guarantee uniqueness.
    """
    from werkzeug.utils import secure_filename
    safe = secure_filename(filename) or "document"
    return f"{uuid.uuid4().hex}_{safe}"


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document. Pipeline:
    1. Validate extension + MIME + size
    2. Save to user-isolated directory with sanitized filename
    3. Extract text
    4. AI categorization (GPT-4o-mini)
    5. Store embedding in ChromaDB
    6. Persist metadata to SQLite
    7. Write audit log
    """
    check_rate_limit(request, "upload")

    # ── 1. VALIDATE FILE ──────────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{suffix}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {os.getenv('MAX_FILE_SIZE_MB', '10')} MB.",
        )

    # ── 2. SAVE FILE SECURELY ────────────────────────────────────────────────
    stored_filename = _sanitize_filename(file.filename or "document" + suffix)
    user_dir = _get_user_upload_dir(current_user.id)
    file_path = user_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(content)

    # ── 3. CREATE DB RECORD (status=processing) ──────────────────────────────
    doc = Document(
        user_id=current_user.id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_type=suffix.lstrip("."),
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # ── 4. EXTRACT TEXT ──────────────────────────────────────────────────
        text = extract_text(str(file_path))

        # ── 5. AI CATEGORIZATION ─────────────────────────────────────────────
        meta = categorize_document(text, filename=file.filename or stored_filename)

        # ── 6. EMBED + STORE IN VECTOR DB ────────────────────────────────────
        vector = add_document(
            user_id=current_user.id,
            doc_id=doc.id,
            text=text,
            metadata=meta,
        )

        # ── 7. UPDATE DB RECORD ───────────────────────────────────────────────
        doc.extracted_text = text[:5000]  # Store first 5k chars
        doc.embedding = vector
        doc.category = meta["category"]
        doc.title = meta["title"]
        doc.summary = meta["summary"]
        doc.skills = meta["skills"]
        doc.doc_date = meta["date"]
        doc.organization = meta["organization"]
        doc.status = "ready"
        db.commit()

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    # ── 8. AUDIT LOG ─────────────────────────────────────────────────────────
    db.add(AuditLog(
        user_id=current_user.id,
        action="upload",
        resource_type="document",
        resource_id=doc.id,
        detail=f"Uploaded: {doc.original_filename}",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "skills": doc.skills,
        "date": doc.doc_date,
        "organization": doc.organization,
        "summary": doc.summary,
        "status": doc.status,
    }
