"""Database engine and session management.

PostgreSQL is the target database. If the configured server cannot be reached at
startup and `DATABASE_FALLBACK_SQLITE` is enabled, the application falls back to a
local SQLite file so the API stays usable during development. The active backend is
always reported by `GET /api/health/db`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseState:
    """Snapshot of which database the application actually connected to."""

    dialect: str
    url: str
    connected: bool
    fallback: bool = False
    error: str | None = None

    @property
    def safe_url(self) -> str:
        """URL with credentials stripped, safe to expose over HTTP."""
        if "@" not in self.url:
            return self.url
        scheme, _, rest = self.url.partition("://")
        return f"{scheme}://***@{rest.rpartition('@')[2]}"


def fallback_allowed() -> bool:
    """Whether degrading to SQLite is permitted.

    The SQLite fallback is a DEVELOPMENT convenience only. Outside a development
    environment a missing database must surface as a failure: silently writing
    stock movements to a local file while the real database is down would
    corrupt the inventory record.
    """
    return settings.DATABASE_FALLBACK_SQLITE and settings.is_development


def _try_connect(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _build_engine() -> tuple[Engine, DatabaseState]:
    url = settings.DATABASE_URL
    try:
        engine = create_engine(url, pool_pre_ping=True, echo=settings.SQL_ECHO, future=True)
        _try_connect(engine)
        logger.info("Connected to database (%s)", engine.dialect.name)
        return engine, DatabaseState(dialect=engine.dialect.name, url=url, connected=True)
    except Exception as exc:  # noqa: BLE001 - any driver error must be reportable
        if not fallback_allowed():
            reason = (
                "SQLite fallback disabled"
                if not settings.DATABASE_FALLBACK_SQLITE
                else f"SQLite fallback refused outside development (ENVIRONMENT={settings.ENVIRONMENT})"
            )
            logger.error("Database unreachable - %s: %s", reason, exc)
            engine = create_engine(url, pool_pre_ping=True, future=True)
            return engine, DatabaseState(
                dialect=engine.dialect.name,
                url=url,
                connected=False,
                error=f"{reason}: {exc}",
            )

        logger.warning("PostgreSQL unreachable (%s). Falling back to SQLite.", exc.__class__.__name__)
        engine = create_engine(
            settings.sqlite_url,
            connect_args={"check_same_thread": False},
            echo=settings.SQL_ECHO,
            future=True,
        )
        _try_connect(engine)
        return engine, DatabaseState(
            dialect=engine.dialect.name,
            url=settings.sqlite_url,
            connected=True,
            fallback=True,
            error=str(exc),
        )


engine, db_state = _build_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping() -> bool:
    """Return True when a trivial query succeeds against the active engine."""
    try:
        _try_connect(engine)
        return True
    except Exception:  # noqa: BLE001
        return False
