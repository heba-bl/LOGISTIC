"""Record who is looking after which alert.

The panel showed forty-four critical alerts and offered nothing to do about
them. They were the same forty-four the next day, and the day after: nothing
recorded that a manager had seen one, called the supplier, and was waiting for
Thursday's delivery. So the count only grew, and a panel whose count only grows
stops being read - which is exactly how the one that mattered gets missed.

This table holds supervision decisions, never business ones. Acknowledging an
alert does not release a lot, move stock or validate a line: those belong to
the shared workbook and to the zone chief who signs them. It records who is
watching, since when, and until when.

Revision ID: 0009_alert_acknowledgements
Revises: 0008_blocked_reason_key
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_alert_acknowledgements"
down_revision = "0008_blocked_reason_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_acknowledgements",
        sa.Column("id", sa.Integer(), primary_key=True),
        # The alert's own key - `redcage-42`, `req-118`. Not a foreign key:
        # an alert is derived, it has no row of its own to point at.
        sa.Column("alert_key", sa.String(length=64), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "ACKNOWLEDGED",
                "SNOOZED",
                "CLOSED",
                "REOPENED",
                name="alertaction",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_reference", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_alert_acknowledgements_alert_key", "alert_acknowledgements", ["alert_key"]
    )
    op.create_index(
        "ix_alert_acknowledgements_action", "alert_acknowledgements", ["action"]
    )
    op.create_index(
        "ix_alert_acknowledgements_actor_id", "alert_acknowledgements", ["actor_id"]
    )
    # The panel reads the newest decision per alert, so the index that matters
    # is the one that orders them.
    op.create_index(
        "ix_alert_acknowledgements_created_at", "alert_acknowledgements", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_alert_acknowledgements_created_at", "alert_acknowledgements")
    op.drop_index("ix_alert_acknowledgements_actor_id", "alert_acknowledgements")
    op.drop_index("ix_alert_acknowledgements_action", "alert_acknowledgements")
    op.drop_index("ix_alert_acknowledgements_alert_key", "alert_acknowledgements")
    op.drop_table("alert_acknowledgements")
