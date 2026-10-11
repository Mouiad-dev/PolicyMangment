from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import (
    ActivatorMixin,
    CreatedAtMixin,
    IntIdMixin,
    TableNameMixin,
    TimestampMixin,
    UpdatedAtMixin,
)


class ProductCode(StrEnum):
    CAR = "CAR"
    HOME = "HOME"


class ValueType(StrEnum):
    DECIMAL = "DECIMAL"
    INT = "INT"
    TEXT = "TEXT"
    BOOL = "BOOL"


class Product(IntIdMixin, TimestampMixin, ActivatorMixin, TableNameMixin, Base):
    __table_args__ = (CheckConstraint("code IN ('CAR','HOME')", name="code"),)

    code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode, native_enum=False, length=10), unique=True
    )
    name: Mapped[str] = mapped_column(String(80))

    plans: Mapped[list[Plan]] = relationship(back_populates="product", lazy="raise")
    addons: Mapped[list[Addon]] = relationship(back_populates="product", lazy="raise")


class Plan(IntIdMixin, TimestampMixin, ActivatorMixin, TableNameMixin, Base):
    __table_args__ = (UniqueConstraint("product_id", "code"),)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))

    product: Mapped[Product] = relationship(back_populates="plans", lazy="raise")
    rates: Mapped[list[Rate]] = relationship(back_populates="plan", lazy="raise")


class Addon(IntIdMixin, TimestampMixin, ActivatorMixin, TableNameMixin, Base):
    __table_args__ = (
        UniqueConstraint("product_id", "code"),
        CheckConstraint("price >= 0", name="price_non_negative"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal]

    product: Mapped[Product] = relationship(back_populates="addons", lazy="raise")


class Rate(IntIdMixin, CreatedAtMixin, TableNameMixin, Base):
    """Never updated: a new price is a new row with a new valid_from (DATA-09)."""

    __table_args__ = (
        UniqueConstraint("plan_id", "band", "valid_from"),
        CheckConstraint("base_price >= 0", name="base_price_non_negative"),
    )

    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="RESTRICT"), index=True)
    band: Mapped[str] = mapped_column(String(40))
    base_price: Mapped[Decimal]
    valid_from: Mapped[date]
    created_by: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )

    plan: Mapped[Plan] = relationship(back_populates="rates", lazy="raise")


class Setting(UpdatedAtMixin, TableNameMixin, Base):
    """App-wide key/value (tax_rate, stamp_duty, cancel_fee...); value is parsed by value_type."""

    __table_args__ = (
        CheckConstraint("value_type IN ('DECIMAL','INT','TEXT','BOOL')", name="value_type"),
    )

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
    value_type: Mapped[ValueType] = mapped_column(Enum(ValueType, native_enum=False, length=10))
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="RESTRICT"), index=True
    )
