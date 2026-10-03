from typing import Any

from policydesk.core.db.uow import FakeUnitOfWork, SqlAlchemyUnitOfWork


async def test_fake_commit_sets_committed() -> None:
    async with FakeUnitOfWork() as uow:
        await uow.commit()
    assert uow.committed is True


async def test_fake_exit_without_commit_rolls_back() -> None:
    uow = FakeUnitOfWork()
    async with uow:
        pass
    assert uow.committed is False
    assert uow.rolled_back is True


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")

    async def close(self) -> None:
        self.calls.append("close")


async def test_sqlalchemy_uow_commits_then_closes() -> None:
    session = _RecordingSession()

    def factory() -> Any:
        return session

    async with SqlAlchemyUnitOfWork(factory) as uow:  # type: ignore[arg-type]
        await uow.commit()
    assert session.calls[0] == "commit"
    assert session.calls[-1] == "close"
