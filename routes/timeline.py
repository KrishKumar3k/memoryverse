"""
Timeline route — returns user documents grouped by year for the journey timeline.
Falls back to upload year (created_at) when the document has no extracted date.
"""
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.jwt_handler import get_current_user
from database.db import get_db
from database.models import Document, User

router = APIRouter(prefix="/api", tags=["Timeline"])

CATEGORY_ICONS = {
    "Certificate": "🏆",
    "Resume":      "📄",
    "Project":     "💡",
    "Internship":  "🏢",
    "Achievement": "⭐",
    "Academic":    "🎓",
    "Other":       "📁",
}


@router.get("/timeline")
def get_timeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the user's documents organized into a year-based timeline.
    - Documents with an extracted doc_date are grouped by that year.
    - Documents without a date fall back to their upload year (created_at).
    """
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id, Document.status == "ready")
        .order_by(Document.doc_date.desc().nullslast(), Document.created_at.desc())
        .all()
    )

    by_year: dict = defaultdict(list)
    for doc in docs:
        # Prefer extracted doc_date year, fall back to upload year
        if doc.doc_date and len(doc.doc_date) >= 4:
            year = doc.doc_date[:4]
            display_date = doc.doc_date
            date_source = "document"
        elif doc.created_at:
            year = str(doc.created_at.year)
            display_date = doc.created_at.strftime("%Y-%m-%d")
            date_source = "uploaded"
        else:
            year = "Undated"
            display_date = None
            date_source = "unknown"

        by_year[year].append({
            "id": doc.id,
            "title": doc.title or doc.original_filename,
            "category": doc.category or "Other",
            "icon": CATEGORY_ICONS.get(doc.category, "📁"),
            "organization": doc.organization,
            "date": display_date,
            "date_source": date_source,   # "document" | "uploaded" | "unknown"
            "summary": doc.summary,
            "skills": doc.skills or [],
            "uploaded_on": doc.created_at.strftime("%b %d, %Y") if doc.created_at else None,
        })

    # Sort years descending (most recent first), keep 'Undated' at end
    sorted_years = sorted(
        [y for y in by_year.keys() if y != "Undated"],
        reverse=True,
    )
    if "Undated" in by_year:
        sorted_years.append("Undated")

    return {
        "timeline": [
            {"year": year, "events": by_year[year]}
            for year in sorted_years
        ]
    }
