from typing import Any

import pytest

from policydesk.core.db.repository import BaseRepository
from policydesk.core.errors import NotFound
from policydesk.modules.auth.models import UserAccount


class UserRepository(BaseRepository[UserAccount]):
    model = UserAccount


class _EmptySession:
    async def get(self, model: Any, id: Any) -> None:
        return None


async def test_get_or_raise_raises_not_found() -> None:
    repo = UserRepository(_EmptySession())  # type: ignore[arg-type]
    with pytest.raises(NotFound):
        await repo.get_or_raise(1)


async def test_get_returns_none_when_missing() -> None:
    repo = UserRepository(_EmptySession())  # type: ignore[arg-type]
    assert await repo.get(1) is None
