"""Phase 1 baseline - schema intentionally empty.

The business data model (suppliers, parts, lots, receptions, inspections,
quality validations, stock, movements, production requests, audit log) is
introduced in Phase 2 as migration 0002.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-19
"""

from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: establishes the migration baseline for the project."""


def downgrade() -> None:
    """No-op."""
