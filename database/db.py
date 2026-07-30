from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

if os.getenv("VERCEL"):
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/memoryverse.db")
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./memoryverse.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,
)

# Enable WAL mode for better SQLite concurrency
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get DB session (use in FastAPI Depends)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables on startup."""
    from database.models import User, Document, Relationship, AuditLog  # noqa
    Base.metadata.create_all(bind=engine)
