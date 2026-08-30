"""Store a validation-code digest for the responsibles who may sign off.

The shared workbook asks a manager for a code before it will move a line to
VALIDE, and the server checks that same code again when the row arrives. Neither
side stores the code itself: both hold `sha256(MATRICULE:code:salt)`, so the
column below is useless to anyone who reads it.

Revision ID: 0005_validation_code
Revises: 0004_vehicle_bom
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_validation_code"
down_revision = "0004_vehicle_bom"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("validation_code_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "validation_code_hash")
