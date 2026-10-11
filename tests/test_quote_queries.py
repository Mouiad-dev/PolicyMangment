from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from policydesk.modules.catalogs.models import Addon, Plan, Product
from policydesk.modules.quotes.models import (
    Quote,
    QuoteAddon,
    QuoteEvent,
    QuoteStatus,
    QuoteVersion,
)


async def _car(session: AsyncSession) -> tuple[Plan, list[Addon]]:
    car = Product(code="CAR", name="Car insurance")
    plan = Plan(code="COMPREHENSIVE", name="Comprehensive")
    addons = [
        Addon(code="WINDSCREEN", name="Windscreen", price=Decimal("100.00")),
        Addon(code="FLOOD", name="Flood", price=Decimal("50.00")),
    ]
    car.plans = [plan]
    car.addons = addons
    session.add(car)
    await session.flush()
    return plan, addons


async def test_new_quote_gets_db_defaults(db_session: AsyncSession) -> None:
    plan, _ = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    db_session.add(quote)
    await db_session.flush()

    assert quote.status == QuoteStatus.DRAFT
    assert quote.risk_details == {}
    assert quote.version == 1
    in_30_days = datetime.now(UTC) + timedelta(days=30)
    assert abs(quote.expires_at - in_30_days) < timedelta(minutes=1)


async def test_priced_quote_needs_start_date(db_session: AsyncSession) -> None:
    plan, _ = await _car(db_session)
    db_session.add(Quote(number="QTE-2026-000001", plan_id=plan.id, status=QuoteStatus.PRICED))

    with pytest.raises(IntegrityError, match="ck_quote_start_date_when_priced"):
        await db_session.flush()


async def test_declined_quote_needs_note(db_session: AsyncSession) -> None:
    plan, _ = await _car(db_session)
    db_session.add(
        Quote(
            number="QTE-2026-000001",
            plan_id=plan.id,
            status=QuoteStatus.DECLINED,
            start_date=date(2026, 11, 1),
        )
    )

    with pytest.raises(IntegrityError, match="ck_quote_decline_note"):
        await db_session.flush()


async def test_same_addon_twice_on_one_quote_is_blocked(db_session: AsyncSession) -> None:
    plan, addons = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    db_session.add(quote)
    await db_session.flush()
    db_session.add_all(
        QuoteAddon(quote_id=quote.id, addon_id=addons[0].id, price=Decimal("100.00"))
        for _ in range(2)
    )

    with pytest.raises(IntegrityError, match="pk_quote_addon"):
        await db_session.flush()


async def test_deleting_a_quote_deletes_its_addon_rows(db_session: AsyncSession) -> None:
    plan, addons = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    quote.addons = [QuoteAddon(addon_id=a.id, price=a.price) for a in addons]
    db_session.add(quote)
    await db_session.flush()

    await db_session.delete(quote)
    await db_session.flush()

    assert await db_session.scalar(select(func.count()).select_from(QuoteAddon)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Addon)) == 2  # catalog stays


@pytest.mark.query_count
async def test_quotes_with_addons_use_two_queries(
    db_session: AsyncSession, sql_log: list[str]
) -> None:
    plan, addons = await _car(db_session)
    for n in range(1, 4):
        quote = Quote(number=f"QTE-2026-{n:06d}", plan_id=plan.id)
        quote.addons = [QuoteAddon(addon_id=a.id, price=a.price) for a in addons]
        db_session.add(quote)
    await db_session.flush()
    db_session.expunge_all()
    sql_log.clear()

    quotes = (await db_session.scalars(select(Quote).options(selectinload(Quote.addons)))).all()

    assert sum(len(q.addons) for q in quotes) == 6
    assert len(sql_log) == 2  # 1 for quotes + 1 for ALL their add-on rows


async def test_capture_saves_quote_and_addons_as_json(db_session: AsyncSession) -> None:
    plan, addons = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id, net_premium=Decimal("1234.50"))
    quote.addons = [QuoteAddon(addon_id=a.id, price=a.price) for a in addons]
    db_session.add(quote)
    await db_session.flush()

    db_session.add(QuoteVersion.capture(quote, 1, QuoteEvent.CREATED, changed_by=None))
    await db_session.flush()
    db_session.expunge_all()

    saved = (await db_session.scalars(select(QuoteVersion))).one()
    assert saved.snapshot["number"] == "QTE-2026-000001"
    assert saved.snapshot["net_premium"] == "1234.50"  # Decimal kept as exact text
    assert saved.snapshot["status"] == "DRAFT"
    assert {a["price"] for a in saved.snapshot["addons"]} == {"100.00", "50.00"}


async def test_same_version_no_twice_is_blocked(db_session: AsyncSession) -> None:
    plan, _ = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    quote.addons = []
    db_session.add(quote)
    await db_session.flush()
    db_session.add_all(
        QuoteVersion.capture(quote, 1, event, changed_by=None)
        for event in (QuoteEvent.CREATED, QuoteEvent.PRICED)
    )

    with pytest.raises(IntegrityError, match="pk_quote_version"):
        await db_session.flush()


async def test_quote_with_history_cannot_be_deleted(db_session: AsyncSession) -> None:
    plan, _ = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    quote.addons = []
    db_session.add(quote)
    await db_session.flush()
    db_session.add(QuoteVersion.capture(quote, 1, QuoteEvent.CREATED, changed_by=None))
    await db_session.flush()

    await db_session.delete(quote)
    with pytest.raises(IntegrityError, match="fk_quote_version_quote_id_quote"):
        await db_session.flush()


@pytest.mark.query_count
async def test_quote_with_versions_uses_two_queries(
    db_session: AsyncSession, sql_log: list[str]
) -> None:
    plan, _ = await _car(db_session)
    quote = Quote(number="QTE-2026-000001", plan_id=plan.id)
    quote.addons = []
    db_session.add(quote)
    await db_session.flush()
    for no, event in enumerate([QuoteEvent.CREATED, QuoteEvent.PRICED, QuoteEvent.ACCEPTED], 1):
        db_session.add(QuoteVersion.capture(quote, no, event, changed_by=None))
    await db_session.flush()
    db_session.expunge_all()
    sql_log.clear()

    stmt = select(Quote).options(selectinload(Quote.versions))
    loaded = (await db_session.scalars(stmt)).one()

    assert [v.event for v in sorted(loaded.versions, key=lambda v: v.version_no)] == [
        QuoteEvent.CREATED,
        QuoteEvent.PRICED,
        QuoteEvent.ACCEPTED,
    ]
    assert len(sql_log) == 2
