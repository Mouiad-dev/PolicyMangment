from sqlalchemy.ext.asyncio import AsyncSession

from policydesk.core.db.base import Base
from policydesk.core.errors import NotFound


class BaseRepository[ModelT: Base]:
    """Tiny CRUD over one aggregate. Child classes set `model` and add queries."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: int) -> ModelT:
        obj = await self.get(id)
        if obj is None:
            raise NotFound(f"{self.model.__name__} {id} not found")
        return obj

    def add(self, obj: ModelT) -> None:
        self.session.add(obj)

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
