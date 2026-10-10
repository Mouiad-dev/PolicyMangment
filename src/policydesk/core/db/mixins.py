from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Identity, Uuid, func, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TableNameMixin:
    @declared_attr.directive
    def __tablename__(cls: type[Any]) -> str:
        from policydesk.shared.utils import camel_to_snake

        return camel_to_snake(cls.__name__)


class IntIdMixin:
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)


class UuidIdMixin:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """created_at + updated_at (most tables)."""


class ActivatorMixin:
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class VersionMixin:
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        return {"version_id_col": cls.version}


class AuditMixin:
    @declared_attr
    def created_by_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("user_account.id"), nullable=True, index=True)

    @declared_attr
    def updated_by_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("user_account.id"), nullable=True, index=True)
