"""Let a recommendation be rendered in the reader's language.

A recommendation was stored as four finished English sentences - title,
message, rationale, action. On a French screen that is the only English left,
and the specification forbids mixing the two on one interface.

The engine now also stores a `text_key` naming the situation it detected. The
interface renders that key with the figures already carried in `metrics_json`,
so the wording lives in the translation catalogue while the reasoning stays in
the service. The English sentences remain as the fallback: an older row, or a
case added tomorrow before its translation, still reads correctly instead of
showing a raw key.

Revision ID: 0007_reco_text_key
Revises: 0006_managed_scope
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_reco_text_key"
down_revision = "0006_managed_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_recommendations",
        sa.Column("text_key", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_recommendations", "text_key")
