"""create ticketing core tables

Revision ID: 20260214_0001
Revises:
Create Date: 2026-02-14 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open', 'done')", name="ck_tickets_status_valid"),
        sa.CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL) OR "
            "(status = 'open' AND completed_at IS NULL)",
            name="ck_tickets_completed_at_matches_status",
        ),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "ticket_tags",
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ticket_id", "tag_id", name="pk_ticket_tags"),
    )

    op.create_index("idx_tickets_status", "tickets", ["status"], unique=False)
    op.create_index("idx_ticket_tags_tag_id", "ticket_tags", ["tag_id"], unique=False)
    op.execute("CREATE UNIQUE INDEX uk_tags_name_ci ON tags (LOWER(name))")
    op.execute("CREATE INDEX idx_tickets_title_trgm ON tickets USING gin (title gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tickets_title_trgm")
    op.execute("DROP INDEX IF EXISTS uk_tags_name_ci")
    op.drop_index("idx_ticket_tags_tag_id", table_name="ticket_tags")
    op.drop_index("idx_tickets_status", table_name="tickets")

    op.drop_table("ticket_tags")
    op.drop_table("tags")
    op.drop_table("tickets")
