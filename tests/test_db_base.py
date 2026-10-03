from sqlalchemy.orm import Mapped, mapped_column

from policydesk.core.db.base import Base
from policydesk.core.db.mixins import (
    ActivatorMixin,
    IntIdMixin,
    TableNameMixin,
    TimestampMixin,
    VersionMixin,
)
from policydesk.shared.utils import camel_to_snake


class SampleThing(IntIdMixin, TimestampMixin, ActivatorMixin, VersionMixin, TableNameMixin, Base):
    name: Mapped[str] = mapped_column(nullable=False)


def test_table_name_from_class() -> None:
    assert SampleThing.__tablename__ == "sample_thing"


def test_mixin_columns_present() -> None:
    cols = set(SampleThing.__table__.columns.keys())
    assert {"id", "created_at", "updated_at", "is_active", "version", "name"} <= cols


def test_pk_name_follows_convention() -> None:
    assert SampleThing.__table__.primary_key.name == "pk_sample_thing"


def test_camel_to_snake() -> None:
    assert camel_to_snake("UserAccount") == "user_account"
    assert camel_to_snake("QuoteAddon") == "quote_addon"
