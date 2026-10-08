"""Dev shell with every model pre-imported (like Django's shell_plus).

Run: ``python -m policydesk.shell [--sql]``. IPython lets you ``await`` at the prompt.
"""

import argparse
import inspect
import sys

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

import policydesk.core.db.registry  # noqa: F401  (register every model on Base)
from policydesk.core.config import get_settings
from policydesk.core.db.base import Base
from policydesk.core.db.session import Database

_HELPERS = {
    "select": select,
    "func": func,
    "text": text,
    "and_": and_,
    "or_": or_,
    "selectinload": selectinload,
    "joinedload": joinedload,
}


def _model_names() -> dict[str, object]:
    """Every mapped model, plus other public classes (enums) defined in its module."""
    names: dict[str, object] = {}
    for mapper in Base.registry.mappers:
        module = sys.modules[mapper.class_.__module__]
        for name, obj in vars(module).items():
            if inspect.isclass(obj) and obj.__module__ == module.__name__ and name[0] != "_":
                names[name] = obj
    return names


def build_namespace(db: Database) -> dict[str, object]:
    return {
        **_model_names(),
        **_HELPERS,
        "settings": get_settings(),
        "db": db,
        "session": db.session(),
    }


async def _close(session: AsyncSession, db: Database) -> None:
    await session.close()
    await db.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PolicyDesk dev shell.")
    parser.add_argument("--sql", action="store_true", help="print every SQL statement")
    args = parser.parse_args(argv)
    try:
        from IPython import start_ipython
        from IPython.core.async_helpers import get_asyncio_loop
    except ImportError:
        raise SystemExit("IPython is missing (dev only). Run: uv sync") from None

    db = Database(get_settings())
    db.engine.echo = args.sql
    namespace = build_namespace(db)
    session = namespace["session"]  # keep a reference: IPython clears user_ns on exit
    assert isinstance(session, AsyncSession)
    print("PolicyDesk shell. Loaded:", ", ".join(sorted(namespace)))
    try:
        start_ipython(argv=[], user_ns=namespace)
    finally:
        # Close on IPython's loop: asyncpg connections belong to the loop that opened them.
        loop = get_asyncio_loop()  # type: ignore[no-untyped-call]
        loop.run_until_complete(_close(session, db))


if __name__ == "__main__":
    main()
