"""Separate the vehicle nomenclature from the references the warehouse holds.

The catalogue carries 2 239 references because that is the vehicle's bill of
materials. It was being treated as the stock perimeter, so every reference got a
safety level - including the ones the warehouse never intended to hold. The
shortage analysis then flagged 1 998 references that had simply never been
supplied, drowning the four that genuinely could stop a line: one useful signal
for every 499 false ones.

A plant does not stock every line of its BOM. `is_managed` states which
references it does; the rest stay in the nomenclature, visible and searchable,
but outside the stock rules - a reference nobody replenishes cannot be short.

The backfill marks as managed whatever the database already treats as such: a
reference that has a stock row, or that a lot has ever been received against.
Anything else has its safety level and consumption cleared, because those two
figures only mean something inside the perimeter.

Revision ID: 0006_managed_scope
Revises: 0005_validation_code
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_managed_scope"
down_revision = "0005_validation_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parts",
        sa.Column("is_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Whatever the plant already holds or has received is, by definition, managed.
    op.execute(
        """
        UPDATE parts SET is_managed = TRUE
        WHERE id IN (SELECT part_id FROM stock)
           OR id IN (SELECT part_id FROM lots)
        """
    )

    # Outside the perimeter these two columns describe a replenishment that
    # nobody performs, and the risk model reads them as a promise.
    op.execute(
        """
        UPDATE parts
        SET safety_stock = 0, average_daily_consumption = 0
        WHERE is_managed = FALSE
        """
    )

    op.create_index("ix_parts_is_managed", "parts", ["is_managed"])


def downgrade() -> None:
    op.drop_index("ix_parts_is_managed", table_name="parts")
    op.drop_column("parts", "is_managed")
