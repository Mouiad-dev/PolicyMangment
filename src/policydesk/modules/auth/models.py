from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import (
    ActivatorMixin,
    IntIdMixin,
    TableNameMixin,
    TimestampMixin,
)


class Role(StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    UNDERWRITER = "UNDERWRITER"
    ADMIN = "ADMIN"


class UserAccount(IntIdMixin, TimestampMixin, ActivatorMixin, TableNameMixin, Base):
    __table_args__ = (
        CheckConstraint("role IN ('CUSTOMER','AGENT','UNDERWRITER','ADMIN')", name="role"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20))
