from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# Stable names for every index/unique/check/FK/PK (keeps Alembic diffs clean).
# column_0_N_name joins ALL columns: uq_plan_product_id_code.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # One place for column types: Mapped[Decimal] is always money NUMERIC(12,2).
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        Decimal: Numeric(12, 2),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }
