"""
Knowledge Graph route — returns nodes (documents) + edges (relationships),
triggers AI relationship rebuild, and allows manual creation/deletion of custom connections.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.jwt_handler import get_current_user
from database.db import get_db
from database.models import Document, Relationship, User
from services.relationship import build_relationships

router = APIRouter(prefix="/api/graph", tags=["Knowledge Graph"])

CATEGORY_COLORS = {
    "Certificate": "#f59e0b",
    "Resume":      "#3b82f6",
    "Project":     "#8b5cf6",
    "Internship":  "#10b981",
    "Achievement": "#ef4444",
    "Academic":    "#06b6d4",
    "Other":       "#6b7280",
}


class CreateRelationshipRequest(BaseModel):
    source_doc_id: int
    target_doc_id: int
    relationship_type: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=255)


@router.get("")
def get_graph(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return knowledge graph nodes and edges for the current user."""
    docs = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == "ready",
    ).all()

    relationships = db.query(Relationship).filter(
        Relationship.user_id == current_user.id,
    ).all()

    nodes = [
        {
            "id": d.id,
            "label": d.title or d.original_filename,
            "category": d.category or "Other",
            "color": CATEGORY_COLORS.get(d.category, "#6b7280"),
            "organization": d.organization,
            "date": d.doc_date,
            "skills": d.skills or [],
        }
        for d in docs
    ]

    edges = [
        {
            "source": r.source_doc_id,
            "target": r.target_doc_id,
            "label": r.relationship_type,
            "description": r.description,
        }
        for r in relationships
    ]

    return {"nodes": nodes, "edges": edges}


@router.post("/rebuild", status_code=status.HTTP_202_ACCEPTED)
def rebuild_graph(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-run the relationship engine on all user documents.
    Clears existing relationships and rebuilds from scratch.
    """
    docs = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == "ready",
    ).all()

    if len(docs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least 2 documents before building the knowledge graph.",
        )

    # Clear old relationships
    db.query(Relationship).filter(Relationship.user_id == current_user.id).delete()
    db.commit()

    # Build new relationships
    doc_dicts = [
        {
            "id": d.id,
            "category": d.category,
            "title": d.title,
            "skills": d.skills or [],
            "organization": d.organization,
            "date": d.doc_date,
        }
        for d in docs
    ]
    relationships = build_relationships(doc_dicts)

    # Persist
    for r in relationships:
        db.add(Relationship(
            user_id=current_user.id,
            source_doc_id=r["source_doc_id"],
            target_doc_id=r["target_doc_id"],
            relationship_type=r["relationship_type"],
            description=r["description"],
        ))
    db.commit()

    return {"message": f"Graph rebuilt with {len(relationships)} relationships."}


@router.post("/relationship", status_code=status.HTTP_201_CREATED)
def create_manual_relationship(
    req: CreateRelationshipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually connect two documents with a custom relationship type."""
    if req.source_doc_id == req.target_doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot connect a document to itself.",
        )

    # Verify both docs belong to current user
    source_doc = db.query(Document).filter(
        Document.id == req.source_doc_id,
        Document.user_id == current_user.id,
    ).first()

    target_doc = db.query(Document).filter(
        Document.id == req.target_doc_id,
        Document.user_id == current_user.id,
    ).first()

    if not source_doc or not target_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both documents were not found or not owned.",
        )

    # Check if relationship already exists
    existing = db.query(Relationship).filter(
        Relationship.user_id == current_user.id,
        ((Relationship.source_doc_id == req.source_doc_id) & (Relationship.target_doc_id == req.target_doc_id)) |
        ((Relationship.source_doc_id == req.target_doc_id) & (Relationship.target_doc_id == req.source_doc_id))
    ).first()

    if existing:
        existing.relationship_type = req.relationship_type
        existing.description = req.description
    else:
        rel = Relationship(
            user_id=current_user.id,
            source_doc_id=req.source_doc_id,
            target_doc_id=req.target_doc_id,
            relationship_type=req.relationship_type,
            description=req.description,
        )
        db.add(rel)

    db.commit()
    return {"message": "Relationship created successfully."}


@router.delete("/relationship/{source_id}/{target_id}", status_code=status.HTTP_200_OK)
def delete_manual_relationship(
    source_id: int,
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific relationship between two documents."""
    rels = db.query(Relationship).filter(
        Relationship.user_id == current_user.id,
        ((Relationship.source_doc_id == source_id) & (Relationship.target_doc_id == target_id)) |
        ((Relationship.source_doc_id == target_id) & (Relationship.target_doc_id == source_id))
    ).all()

    if not rels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    for r in rels:
        db.delete(r)
    db.commit()

    return {"message": "Relationship deleted successfully."}
