from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from policydesk.modules.auth.models import Role, UserAccount
from policydesk.modules.catalogs.models import Addon, Plan, Product, Rate

CAR_PLANS = ["THIRD_PARTY", "THIRD_PARTY_FIRE_THEFT", "COMPREHENSIVE"]
HOME_PLANS = ["BUILDING", "CONTENTS", "BUILDING_AND_CONTENTS"]


async def _seed_products(session: AsyncSession) -> None:
    for code, plans in [("CAR", CAR_PLANS), ("HOME", HOME_PLANS)]:
        product = Product(code=code, name=f"{code} insurance")
        product.plans = [Plan(code=p, name=p.title()) for p in plans]
        session.add(product)
    await session.flush()
    session.expunge_all()  # forget loaded objects, so the next read really hits the DB


async def _admin(session: AsyncSession) -> UserAccount:
    admin = UserAccount(email="admin@test.com", password_hash="x", full_name="A", role=Role.ADMIN)
    session.add(admin)
    await session.flush()
    return admin


@pytest.mark.query_count
async def test_products_with_plans_use_two_queries(
    db_session: AsyncSession, sql_log: list[str]
) -> None:
    await _seed_products(db_session)
    sql_log.clear()

    stmt = select(Product).options(selectinload(Product.plans)).order_by(Product.code)
    products = (await db_session.scalars(stmt)).all()
    plan_codes = {p.code: sorted(plan.code for plan in p.plans) for p in products}

    assert plan_codes == {"CAR": sorted(CAR_PLANS), "HOME": sorted(HOME_PLANS)}
    assert len(sql_log) == 2  # 1 for products + 1 for ALL their plans, never 1 + N


async def test_reading_unloaded_relationship_raises(db_session: AsyncSession) -> None:
    await _seed_products(db_session)
    car = (await db_session.scalars(select(Product).where(Product.code == "CAR"))).one()

    with pytest.raises(InvalidRequestError, match="lazy='raise'"):
        _ = car.plans


async def test_same_plan_code_twice_in_one_product_is_blocked(db_session: AsyncSession) -> None:
    await _seed_products(db_session)
    car = (await db_session.scalars(select(Product).where(Product.code == "CAR"))).one()
    db_session.add(Plan(product_id=car.id, code="COMPREHENSIVE", name="Again"))

    with pytest.raises(IntegrityError, match="uq_plan_product_id_code"):
        await db_session.flush()


async def test_same_addon_code_in_two_products_is_allowed(db_session: AsyncSession) -> None:
    await _seed_products(db_session)
    products = (await db_session.scalars(select(Product))).all()
    db_session.add_all(
        Addon(product_id=p.id, code="FLOOD", name="Flood", price=Decimal("50.00")) for p in products
    )
    await db_session.flush()


async def test_negative_addon_price_is_blocked(db_session: AsyncSession) -> None:
    await _seed_products(db_session)
    car = (await db_session.scalars(select(Product).where(Product.code == "CAR"))).one()
    db_session.add(Addon(product_id=car.id, code="FLOOD", name="Flood", price=Decimal("-1.00")))

    with pytest.raises(IntegrityError, match="ck_addon_price_non_negative"):
        await db_session.flush()


async def test_unknown_product_code_is_blocked(db_session: AsyncSession) -> None:
    db_session.add(Product(code="BIKE", name="Bike"))

    with pytest.raises(IntegrityError, match="ck_product_code"):
        await db_session.flush()


async def test_rate_lookup_takes_latest_valid_from(db_session: AsyncSession) -> None:
    await _seed_products(db_session)
    admin = await _admin(db_session)
    plan = (await db_session.scalars(select(Plan).where(Plan.code == "COMPREHENSIVE"))).one()
    for valid_from, price in [(date(2026, 1, 1), "900.00"), (date(2026, 7, 1), "950.00")]:
        db_session.add(
            Rate(
                plan_id=plan.id,
                band="V_50K_100K",
                base_price=Decimal(price),
                valid_from=valid_from,
                created_by=admin.id,
            )
        )
    await db_session.flush()

    async def price_on(day: date) -> Decimal:
        stmt = (
            select(Rate.base_price)
            .where(Rate.plan_id == plan.id, Rate.band == "V_50K_100K", Rate.valid_from <= day)
            .order_by(Rate.valid_from.desc())
            .limit(1)
        )
        return (await db_session.scalars(stmt)).one()

    assert await price_on(date(2026, 3, 15)) == Decimal("900.00")  # old price stays for old dates
    assert await price_on(date(2026, 8, 1)) == Decimal("950.00")
