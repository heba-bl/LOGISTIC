"""Human-readable business references (LOT-2026-0001, PR-2026-0007, ...).

References are generated from the current row count per entity inside the same
transaction as the insert, so they stay dense and predictable in a single-writer
simulation context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.flow import Inspection, Lot, Reception
from app.models.production import ProductionRequest
from app.models.warehouse import StockMovement


def _year() -> int:
    return datetime.now(timezone.utc).year


def _next(db: Session, model, column, prefix: str, width: int = 3) -> str:
    year = _year()
    like = f"{prefix}-{year}-%"
    count = db.execute(
        select(func.count()).select_from(model).where(column.like(like))
    ).scalar_one()
    return f"{prefix}-{year}-{count + 1:0{width}d}"


def next_lot_number(db: Session) -> str:
    return _next(db, Lot, Lot.lot_number, "LOT")


def next_reception_reference(db: Session) -> str:
    return _next(db, Reception, Reception.reference, "RCP")


def next_inspection_reference(db: Session) -> str:
    return _next(db, Inspection, Inspection.reference, "INS")


def next_request_reference(db: Session) -> str:
    return _next(db, ProductionRequest, ProductionRequest.reference, "PR")


def next_movement_reference(db: Session) -> str:
    return _next(db, StockMovement, StockMovement.reference, "MOV", width=5)
