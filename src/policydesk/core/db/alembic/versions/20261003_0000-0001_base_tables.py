"""base tables: user_account, outbox_message, processed_event

Revision ID: 0001
Revises:
Create Date: 2026-10-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('CUSTOMER','AGENT','UNDERWRITER','ADMIN')",
            name="role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_account"),
        sa.UniqueConstraint("email", name="uq_user_account_email"),
    )

    op.create_table(
        "outbox_message",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_type", sa.String(length=30), nullable=False),
        sa.Column("aggregate_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("next_try_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="attempts"),
        sa.CheckConstraint(
            "status IN ('PENDING','SENT','FAILED')",
            name="status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_message"),
    )
    op.create_index(
        "ix_outbox_message_pending",
        "outbox_message",
        ["next_try_at"],
        unique=False,
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    op.create_table(
        "processed_event",
        sa.Column("handler", sa.String(length=80), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("handler", "event_id", name="pk_processed_event"),
    )


def downgrade() -> None:
    op.drop_table("processed_event")
    op.drop_index("ix_outbox_message_pending", table_name="outbox_message")
    op.drop_table("outbox_message")
    op.drop_table("user_account")
