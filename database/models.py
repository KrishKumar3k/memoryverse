from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database.db import Base


class User(Base):
    """Registered users — passwords are bcrypt hashed, never stored plain."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    """Uploaded documents with AI-extracted metadata."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Original file info
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)   # sanitized, UUID-prefixed
    file_path = Column(String(1000), nullable=False)        # relative path inside uploads/
    file_type = Column(String(50), nullable=False)          # pdf, docx, txt

    # AI-extracted metadata
    category = Column(String(100), nullable=True)           # Certificate, Project, etc.
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    skills = Column(JSON, nullable=True)                    # list of skill strings
    doc_date = Column(String(50), nullable=True)            # extracted date (YYYY or YYYY-MM)
    organization = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=True)            # raw extracted text
    embedding = Column(JSON, nullable=True)                 # vector embedding floats list

    # Processing status
    status = Column(String(50), default="processing")       # processing | ready | failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="documents")
    source_relationships = relationship(
        "Relationship", foreign_keys="Relationship.source_doc_id",
        cascade="all, delete-orphan"
    )
    target_relationships = relationship(
        "Relationship", foreign_keys="Relationship.target_doc_id",
        cascade="all, delete-orphan"
    )


class Relationship(Base):
    """AI-identified connections between documents (knowledge graph edges)."""
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(200), nullable=False)  # e.g. "Skill → Project"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """Audit trail of all document access/modification events."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)    # upload, download, delete, search, view
    resource_type = Column(String(50), nullable=True)  # document, search
    resource_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")
