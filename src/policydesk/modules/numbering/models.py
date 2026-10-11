from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import TableNameMixin, UpdatedAtMixin
from policydesk.modules.numbering.exceptions import NumberRangeFull


class ObjectType(StrEnum):
    QUOTE = "QUOTE"
    POLICY = "POLICY"
    INVOICE = "INVOICE"
    PRODUCT = "PRODUCT"
    CUSTOMER = "CUSTOMER"


class Numbering(UpdatedAtMixin, TableNameMixin, Base):
    """Number settings + last value per object type, e.g. POLICY -> PLC-2026-000123."""

    __table_args__ = (
        CheckConstraint(
            "object_type IN ('QUOTE','POLICY','INVOICE','PRODUCT','CUSTOMER')", name="object_type"
        ),
        CheckConstraint("prefix ~ '^[A-Z]{2,5}$'", name="prefix_format"),
        CheckConstraint("range_start >= 1", name="range_start"),
        CheckConstraint("range_end > range_start", name="range_valid"),
        CheckConstraint("padding BETWEEN 1 AND 8", name="padding"),
        CheckConstraint("current_year >= 2026", name="current_year"),
        CheckConstraint(
            "last_value BETWEEN range_start - 1 AND range_end", name="last_value_in_range"
        ),
    )

    object_type: Mapped[ObjectType] = mapped_column(
        Enum(ObjectType, native_enum=False, length=20), primary_key=True
    )
    prefix: Mapped[str] = mapped_column(String(5))
    year_in_number: Mapped[bool] = mapped_column(default=True, server_default="true")
    range_start: Mapped[int] = mapped_column(default=1, server_default="1")
    range_end: Mapped[int] = mapped_column(default=999999, server_default="999999")
    padding: Mapped[int] = mapped_column(SmallInteger, default=6, server_default="6")
    current_year: Mapped[int] = mapped_column(SmallInteger)
    last_value: Mapped[int]

    def format(self, value: int, year: int) -> str:
        digits = str(value).zfill(self.padding)
        return f"{self.prefix}-{year}-{digits}" if self.year_in_number else f"{self.prefix}{digits}"

    def take_next(self, today: date) -> str:
        """Bump the counter and return the new number. Call it only on a row locked FOR UPDATE."""
        if today.year != self.current_year:
            self.current_year = today.year
            self.last_value = self.range_start - 1
        if self.last_value >= self.range_end:
            raise NumberRangeFull(f"{self.object_type} number range is full")
        self.last_value += 1
        return self.format(self.last_value, self.current_year)
