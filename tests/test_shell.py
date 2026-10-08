from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policydesk.core.config import get_settings
from policydesk.core.db.session import Database
from policydesk.core.events.models import OutboxMessage
from policydesk.modules.auth.models import Role, UserAccount
from policydesk.shell import build_namespace


async def test_namespace_has_models_helpers_and_session() -> None:
    db = Database(get_settings())
    namespace = build_namespace(db)
    session = namespace["session"]
    assert isinstance(session, AsyncSession)
    try:
        assert namespace["UserAccount"] is UserAccount
        assert namespace["OutboxMessage"] is OutboxMessage  # found via the registry
        assert namespace["Role"] is Role  # other public names of a model module
        assert namespace["select"] is select
        assert namespace["db"] is db
    finally:
        await session.close()
        await db.dispose()
