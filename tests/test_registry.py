from policydesk.core.db import registry
from policydesk.core.db.base import Base


def test_base_tables_present() -> None:
    tables = set(Base.metadata.tables)
    assert {"user_account", "outbox_message", "processed_event"} <= tables


def test_registry_exposes_models() -> None:
    assert registry.UserAccount.__tablename__ == "user_account"
    assert registry.OutboxMessage.__tablename__ == "outbox_message"
    assert registry.ProcessedEvent.__tablename__ == "processed_event"


def test_constraint_names_follow_convention() -> None:
    user = Base.metadata.tables["user_account"]
    names = {c.name for c in user.constraints}
    assert "pk_user_account" in names
    assert "ck_user_account_role" in names


def test_processed_event_composite_pk() -> None:
    pe = Base.metadata.tables["processed_event"]
    pk_cols = [c.name for c in pe.primary_key.columns]
    assert pk_cols == ["handler", "event_id"]
