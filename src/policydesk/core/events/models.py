from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import CreatedAtMixin, TableNameMixin, UuidIdMixin


class OutboxMessage(UuidIdMixin, CreatedAtMixin, TableNameMixin, Base):
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','SENT','FAILED')", name="status"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index(
            "ix_outbox_message_pending",
            "next_try_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    event_type: Mapped[str] = mapped_column(String(40))
    aggregate_type: Mapped[str] = mapped_column(String(30))
    aggregate_id: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'PENDING'"))
    next_try_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(TableNameMixin, Base):
    handler: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
