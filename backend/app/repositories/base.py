"""Generic repository providing the CRUD primitives shared by every entity.

Phase 2 repositories subclass this (e.g. `LotRepository(BaseRepository[Lot])`)
and add domain-specific queries.
"""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Thin, typed wrapper around a SQLAlchemy Session for one model."""

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, entity_id: Any) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)

    def commit(self) -> None:
        self.db.commit()
