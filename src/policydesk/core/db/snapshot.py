from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import inspect


def to_snapshot(obj: Any) -> dict[str, Any]:
    """Column values of a loaded ORM object as JSON-safe values (for history rows)."""
    return {
        attr.key: _json_safe(getattr(obj, attr.key)) for attr in inspect(obj).mapper.column_attrs
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal | UUID):
        return str(value)  # Decimal as text keeps every digit; float would not
    if isinstance(value, date):  # also datetime
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
