"""
SQLAlchemy database setup.

Provides:
- engine   : the connection pool to PostgreSQL
- Base     : declarative base for ORM models (db_models.py extends this)
- get_db() : FastAPI Depends() function that yields a Session per request

Usage in an endpoint:
    @app.get("/incidents")
    def list_incidents(db: Session = Depends(get_db)):
        return db.query(IncidentRecordORM).all()

DATABASE_URL is read from the environment variable DB_URL.
Example: postgresql://llmqa:llmqa_dev@localhost:5434/llmqa
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ── Connection URL ─────────────────────────────────────────────────────────────
# Read from environment — never hardcode credentials.
# Default points to the Docker container we started in Step 3.
DATABASE_URL = os.environ.get("DB_URL") or "postgresql://llmqa:llmqa_dev@localhost:5434/llmqa"

# ── Engine ─────────────────────────────────────────────────────────────────────
# `pool_pre_ping=True` automatically reconnects if a connection has gone stale
# (e.g. after the Docker container restarts).
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ── Session factory ────────────────────────────────────────────────────────────
# autocommit=False → we commit explicitly (safer, gives us control)
# autoflush=False  → prevents unexpected SQL during reads
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Declarative Base ───────────────────────────────────────────────────────────
# All ORM model classes in db_models.py inherit from this.
# SQLAlchemy uses it to know which classes map to which tables.
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session for the duration of a single HTTP request.

    The `try/finally` ensures the session is always closed, even if the
    endpoint raises an exception — preventing connection leaks.

    Usage:
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
