from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policydesk.modules.auth.models import Role, UserAccount


async def test_insert_and_read_user(db_session: AsyncSession) -> None:
    db_session.add(
        UserAccount(email="a@test.com", password_hash="x", full_name="A", role=Role.CUSTOMER)
    )
    await db_session.commit()
    found = (
        await db_session.scalars(select(UserAccount).where(UserAccount.email == "a@test.com"))
    ).one()
    assert found.full_name == "A"


async def test_isolation_user_from_other_test_is_gone(db_session: AsyncSession) -> None:
    count = len((await db_session.scalars(select(UserAccount))).all())
    assert count == 0
