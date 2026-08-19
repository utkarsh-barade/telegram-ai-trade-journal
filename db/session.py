"""
SQLAlchemy database session and engine factory.

Usage:
    from db.session import get_db, init_db

    # In FastAPI dependency injection:
    def route(db: Session = Depends(get_db)):
        ...

    # At startup:
    init_db()
"""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────────────

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trade_journal.db")

# SQLite-specific: enable WAL mode and foreign key enforcement
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # Echo SQL in DEBUG — never in production
    echo=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
)

# SQLite: enable foreign keys and WAL journal mode on every connection
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables that do not yet exist.

    Prefer Alembic for production migrations; this function is used for
    development startup and tests.
    """
    Base.metadata.create_all(bind=engine)


# ──────────────────────────────────────────────────────────────────────────────
# Session helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager version for use outside FastAPI (e.g. bot handlers)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
