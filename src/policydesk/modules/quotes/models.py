from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import (
    CreatedAtMixin,
    IntIdMixin,
    TableNameMixin,
    TimestampMixin,
    VersionMixin,
)
from policydesk.core.db.snapshot import to_snapshot

if TYPE_CHECKING:
    from policydesk.modules.catalogs.models import Addon, Plan
    from policydesk.modules.customers.models import Customer


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"
    PRICED = "PRICED"
    REFERRED = "REFERRED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"


class QuoteEvent(StrEnum):
    """Business events that save a row in quote_version."""

    CREATED = "CREATED"
    PRICED = "PRICED"
    REFERRED = "REFERRED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"


def _non_negative(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} >= 0", name=f"{column}_non_negative")


class Quote(IntIdMixin, TimestampMixin, VersionMixin, TableNameMixin, Base):
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PRICED','REFERRED','APPROVED','DECLINED','ACCEPTED','EXPIRED')",
            name="status",
        ),
        # A DRAFT may have no start date yet; every priced status needs one.
        CheckConstraint(
            "status IN ('DRAFT','EXPIRED') OR start_date IS NOT NULL", name="start_date_when_priced"
        ),
        CheckConstraint("status <> 'DECLINED' OR decision_note IS NOT NULL", name="decline_note"),
        _non_negative("net_premium"),
        _non_negative("tax_amount"),
        _non_negative("stamp_duty"),
        _non_negative("total_payable"),
        Index("ix_quote_status_expires_at", "status", "expires_at"),
    )

    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="RESTRICT"), index=True)
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus, native_enum=False, length=12),
        default=QuoteStatus.DRAFT,
        server_default=QuoteStatus.DRAFT.value,
    )
    start_date: Mapped[date | None]
    risk_details: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
    price_snapshot: Mapped[dict[str, Any] | None]
    net_premium: Mapped[Decimal | None]
    tax_amount: Mapped[Decimal | None]
    stamp_duty: Mapped[Decimal | None]
    total_payable: Mapped[Decimal | None]
    referral_reasons: Mapped[list[str] | None] = mapped_column(JSONB)
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(server_default=text("now() + interval '30 days'"))

    customer: Mapped[Customer | None] = relationship(lazy="raise")
    plan: Mapped[Plan] = relationship(lazy="raise")
    # The DB deletes add-on rows with the quote (ON DELETE CASCADE); passive_deletes trusts it.
    addons: Mapped[list[QuoteAddon]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    # History is never changed by the ORM; the DB (RESTRICT) blocks deleting a quote that has it.
    versions: Mapped[list[QuoteVersion]] = relationship(
        back_populates="quote", passive_deletes="all", lazy="raise"
    )


class QuoteAddon(TableNameMixin, Base):
    """Add-on chosen on a quote, with its price at that time (catalog changes don't touch it)."""

    __table_args__ = (_non_negative("price"),)

    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quote.id", ondelete="CASCADE"), primary_key=True
    )
    addon_id: Mapped[int] = mapped_column(
        ForeignKey("addon.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    price: Mapped[Decimal]

    quote: Mapped[Quote] = relationship(back_populates="addons", lazy="raise")
    addon: Mapped[Addon] = relationship(lazy="raise")


class QuoteVersion(CreatedAtMixin, TableNameMixin, Base):
    """Full copy of a quote at a business event (v1, v2, ...). Never updated."""

    __table_args__ = (
        CheckConstraint(
            "event IN ('CREATED','PRICED','REFERRED','APPROVED','DECLINED','ACCEPTED','EXPIRED')",
            name="event",
        ),
        CheckConstraint("version_no >= 1", name="version_no"),
    )

    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quote.id", ondelete="RESTRICT"), primary_key=True
    )
    version_no: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[QuoteEvent] = mapped_column(Enum(QuoteEvent, native_enum=False, length=20))
    snapshot: Mapped[dict[str, Any]]
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )

    quote: Mapped[Quote] = relationship(back_populates="versions", lazy="raise")

    @classmethod
    def capture(
        cls, quote: Quote, version_no: int, event: QuoteEvent, changed_by: int | None
    ) -> QuoteVersion:
        """Build the history row. quote.addons must be loaded (selectinload) or new."""
        snapshot = to_snapshot(quote) | {"addons": [to_snapshot(a) for a in quote.addons]}
        return cls(
            quote_id=quote.id,
            version_no=version_no,
            event=event,
            snapshot=snapshot,
            changed_by=changed_by,
        )
