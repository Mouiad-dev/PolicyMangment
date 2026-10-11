from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import IntIdMixin, TableNameMixin, TimestampMixin

if TYPE_CHECKING:
    from policydesk.modules.auth.models import UserAccount


class IdType(StrEnum):
    MYKAD = "MYKAD"
    PASSPORT = "PASSPORT"


class Customer(IntIdMixin, TimestampMixin, TableNameMixin, Base):
    __table_args__ = (
        CheckConstraint("id_type IN ('MYKAD','PASSPORT')", name="id_type"),
        CheckConstraint("id_type <> 'MYKAD' OR id_number ~ '^[0-9]{12}$'", name="mykad_12_digits"),
        CheckConstraint(r"mobile ~ '^\+60[0-9]{8,10}$'", name="mobile_format"),
        UniqueConstraint("id_type", "id_number"),
    )

    # user_id = own login (0..1), agent_id = selling agent (0..1); both point to user_account.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), unique=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(150))
    id_type: Mapped[IdType] = mapped_column(Enum(IdType, native_enum=False, length=10))
    id_number: Mapped[str] = mapped_column(String(20))
    date_of_birth: Mapped[date]
    email: Mapped[str] = mapped_column(String(254), index=True)
    mobile: Mapped[str] = mapped_column(String(16))

    # lazy="raise": reading a link that was not loaded fails loudly (no N+1 / MissingGreenlet).
    user: Mapped[UserAccount | None] = relationship(foreign_keys=[user_id], lazy="raise")
    agent: Mapped[UserAccount | None] = relationship(foreign_keys=[agent_id], lazy="raise")
    addresses: Mapped[list[Address]] = relationship(back_populates="customer", lazy="raise")


class Address(IntIdMixin, TimestampMixin, TableNameMixin, Base):
    __table_args__ = (CheckConstraint("postcode ~ '^[0-9]{5}$'", name="postcode_format"),)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), index=True
    )
    line1: Mapped[str] = mapped_column(String(150))
    line2: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(80))
    postcode: Mapped[str] = mapped_column(CHAR(5))
    state: Mapped[str] = mapped_column(String(40))

    customer: Mapped[Customer] = relationship(back_populates="addresses", lazy="raise")
