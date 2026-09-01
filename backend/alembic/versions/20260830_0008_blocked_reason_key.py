"""Let a machine-written blocking reason be read in the operator's language.

`lot.blocked_reason` holds two very different things. When a manager blocks a
lot, it is the justification they typed - their words, and translating them
would be wrong. When the services block a lot themselves, it is a sentence the
code composed, and on a French screen it was the only English left.

The generated cases now also store the situation and its figures, so the
interface can word them. The sentence stays: it is what the audit recorded, it
is the fallback for a lot blocked before this change, and it is what a
manager's own justification continues to use.

Revision ID: 0008_blocked_reason_key
Revises: 0007_reco_text_key
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_blocked_reason_key"
down_revision = "0007_reco_text_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("blocked_reason_key", sa.String(length=40), nullable=True))
    op.add_column("lots", sa.Column("blocked_reason_values", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lots", "blocked_reason_values")
    op.drop_column("lots", "blocked_reason_key")
