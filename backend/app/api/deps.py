"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    """Yield a database session and roll back if the request fails.

    Routes commit explicitly once the business operation succeeded, so a failed
    workflow never leaves a partial write behind.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
