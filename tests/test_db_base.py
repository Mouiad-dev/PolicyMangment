import inspect
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from policydesk.core.db.base import NAMING_CONVENTION, Base
from policydesk.core.db.mixins import (
    ActivatorMixin,
    CreatedAtMixin,
    IntIdMixin,
    TableNameMixin,
    TimestampMixin,
    UpdatedAtMixin,
    VersionMixin,
)
from policydesk.core.events.models import OutboxMessage
from policydesk.modules.auth.models import UserAccount
from policydesk.shared.utils import camel_to_snake


class SampleThing(IntIdMixin, TimestampMixin, ActivatorMixin, VersionMixin, TableNameMixin, Base):
    name: Mapped[str] = mapped_column(nullable=False)


def test_table_name_from_class() -> None:
    assert SampleThing.__tablename__ == "sample_thing"


def test_mixin_columns_present() -> None:
    cols = set(SampleThing.__table__.columns.keys())
    assert {"id", "created_at", "updated_at", "is_active", "version", "name"} <= cols


def test_pk_name_follows_convention() -> None:
    assert Base.metadata.tables["sample_thing"].primary_key.name == "pk_sample_thing"


def test_camel_to_snake() -> None:
    assert camel_to_snake("UserAccount") == "user_account"
    assert camel_to_snake("QuoteAddon") == "quote_addon"


# --- M1.1: naming convention with many columns ---


def test_multi_column_names_join_all_columns() -> None:
    md = MetaData(naming_convention=NAMING_CONVENTION)
    plan = Table(
        "plan",
        md,
        Column("product_id", BigInteger),
        Column("code", String(40)),
        UniqueConstraint("product_id", "code"),
    )
    Index(None, plan.c.product_id, plan.c.code)
    unique = next(c for c in plan.constraints if isinstance(c, UniqueConstraint))
    assert unique.name == "uq_plan_product_id_code"
    assert {i.name for i in plan.indexes} == {"ix_plan_product_id_code"}


def test_single_column_names_did_not_change() -> None:
    table = Base.metadata.tables["user_account"]
    assert {c.name for c in table.constraints if isinstance(c, UniqueConstraint)} == {
        "uq_user_account_email"
    }


# --- M1.1: created_at / updated_at mixins ---


def test_timestamp_mixin_is_both_small_mixins() -> None:
    assert issubclass(TimestampMixin, CreatedAtMixin)
    assert issubclass(TimestampMixin, UpdatedAtMixin)


def test_outbox_has_created_at_only() -> None:
    cols = set(OutboxMessage.__table__.columns.keys())
    assert "created_at" in cols
    assert "updated_at" not in cols


def test_no_model_declares_its_own_id_or_timestamps() -> None:
    """PAT-AC-02: id / created_at / updated_at always come from a mixin."""
    for mapper in Base.registry.mappers:
        own = inspect.get_annotations(mapper.class_)
        assert not {"id", "created_at", "updated_at"} & set(own), mapper.class_.__name__


# --- M1.1: identity primary keys ---


def test_int_id_is_identity_not_serial() -> None:
    identity = Base.metadata.tables[UserAccount.__tablename__].c.id.identity
    assert identity is not None  # Postgres: GENERATED ... AS IDENTITY, not BIGSERIAL
    assert identity.always is False  # BY DEFAULT: tests and seeds may still set an id


# --- M1.1: one place for money / time / JSON types ---


class _Probe(DeclarativeBase):
    type_annotation_map = Base.type_annotation_map


class _Priced(_Probe):
    __tablename__ = "priced"
    id: Mapped[int] = mapped_column(primary_key=True)
    price: Mapped[Decimal]
    paid_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


def test_decimal_maps_to_numeric_12_2() -> None:
    price = _Priced.__table__.c.price.type
    assert isinstance(price, Numeric)
    assert (price.precision, price.scale) == (12, 2)


def test_datetime_is_timezone_aware_and_dict_is_jsonb() -> None:
    paid_at = _Priced.__table__.c.paid_at.type
    assert isinstance(paid_at, DateTime)
    assert paid_at.timezone is True
    assert isinstance(_Priced.__table__.c.data.type, JSONB)
