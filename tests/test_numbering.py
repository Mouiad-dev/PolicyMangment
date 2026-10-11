from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from policydesk.core.db.base import Base
from policydesk.modules.numbering.exceptions import NumberRangeFull
from policydesk.modules.numbering.models import Numbering, ObjectType


def _policy_numbering(**overrides: object) -> Numbering:
    values: dict[str, object] = {
        "object_type": ObjectType.POLICY,
        "prefix": "PLC",
        "year_in_number": True,
        "range_start": 1,
        "range_end": 999999,
        "padding": 6,
        "current_year": 2026,
        "last_value": 122,
    }
    return Numbering(**(values | overrides))


def test_take_next_bumps_and_formats() -> None:
    numbering = _policy_numbering()
    assert numbering.take_next(date(2026, 10, 11)) == "PLC-2026-000123"
    assert numbering.take_next(date(2026, 10, 11)) == "PLC-2026-000124"
    assert numbering.last_value == 124


def test_new_year_starts_the_range_again() -> None:
    numbering = _policy_numbering(range_start=100)
    assert numbering.take_next(date(2027, 1, 1)) == "PLC-2027-000100"
    assert numbering.current_year == 2027


def test_number_without_year() -> None:
    numbering = _policy_numbering(year_in_number=False)
    assert numbering.take_next(date(2026, 10, 11)) == "PLC000123"


def test_full_range_raises_and_does_not_bump() -> None:
    numbering = _policy_numbering(range_end=122)
    with pytest.raises(NumberRangeFull, match="POLICY number range is full"):
        numbering.take_next(date(2026, 10, 11))
    assert numbering.last_value == 122


def test_constraint_names() -> None:
    names = {str(c.name) for c in Base.metadata.tables["numbering"].constraints}
    assert {
        "pk_numbering",
        "ck_numbering_object_type",
        "ck_numbering_prefix_format",
        "ck_numbering_range_start",
        "ck_numbering_range_valid",
        "ck_numbering_padding",
        "ck_numbering_current_year",
        "ck_numbering_last_value_in_range",
    } <= names


async def test_migration_seeds_one_row_per_object_type(db_session: AsyncSession) -> None:
    rows = (await db_session.scalars(select(Numbering))).all()
    assert {r.object_type: r.prefix for r in rows} == {
        ObjectType.QUOTE: "QTE",
        ObjectType.POLICY: "PLC",
        ObjectType.INVOICE: "INV",
        ObjectType.PRODUCT: "PRD",
        ObjectType.CUSTOMER: "CUS",
    }
    assert all(r.last_value == r.range_start - 1 for r in rows)


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("prefix", "plc", "ck_numbering_prefix_format"),
        ("padding", 9, "ck_numbering_padding"),
        ("last_value", 1_000_000, "ck_numbering_last_value_in_range"),
    ],
)
async def test_bad_settings_are_blocked(
    db_session: AsyncSession, column: str, value: object, constraint: str
) -> None:
    row = await db_session.get_one(Numbering, ObjectType.POLICY)
    setattr(row, column, value)

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()
