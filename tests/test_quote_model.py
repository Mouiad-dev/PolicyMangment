from sqlalchemy import ForeignKey

from policydesk.core.db.base import Base
from policydesk.modules.quotes.models import Quote, QuoteAddon, QuoteVersion


def _fk(table: str, column: str) -> ForeignKey:
    (fk,) = Base.metadata.tables[table].c[column].foreign_keys
    return fk


def _constraint_names(table: str) -> set[str]:
    return {str(c.name) for c in Base.metadata.tables[table].constraints}


def _index_names(table: str) -> set[str]:
    return {str(i.name) for i in Base.metadata.tables[table].indexes}


def test_quote_constraint_names_follow_srs() -> None:
    assert {
        "pk_quote",
        "uq_quote_number",
        "ck_quote_status",
        "ck_quote_start_date_when_priced",
        "ck_quote_decline_note",
        "ck_quote_net_premium_non_negative",
        "ck_quote_tax_amount_non_negative",
        "ck_quote_stamp_duty_non_negative",
        "ck_quote_total_payable_non_negative",
    } <= _constraint_names("quote")


def test_quote_indexes() -> None:
    assert {
        "ix_quote_customer_id",
        "ix_quote_created_by",
        "ix_quote_agent_id",
        "ix_quote_plan_id",
        "ix_quote_decided_by",
        "ix_quote_status_expires_at",
    } <= _index_names("quote")


def test_quote_foreign_keys_restrict() -> None:
    for column, target in [
        ("customer_id", "customer.id"),
        ("created_by", "user_account.id"),
        ("agent_id", "user_account.id"),
        ("plan_id", "plan.id"),
        ("decided_by", "user_account.id"),
    ]:
        fk = _fk("quote", column)
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"


def test_quote_has_version_for_optimistic_lock() -> None:
    assert "version" in Base.metadata.tables["quote"].c
    assert Quote.__mapper__.version_id_col is not None


def test_quote_addon_composite_pk_and_cascade() -> None:
    table = Base.metadata.tables["quote_addon"]
    assert [c.name for c in table.primary_key] == ["quote_id", "addon_id"]
    assert _fk("quote_addon", "quote_id").ondelete == "CASCADE"
    assert _fk("quote_addon", "addon_id").ondelete == "RESTRICT"
    assert "ix_quote_addon_addon_id" in _index_names("quote_addon")
    assert "ck_quote_addon_price_non_negative" in _constraint_names("quote_addon")


def test_quote_version_pk_checks_and_restrict() -> None:
    table = Base.metadata.tables["quote_version"]
    assert [c.name for c in table.primary_key] == ["quote_id", "version_no"]
    assert {"ck_quote_version_event", "ck_quote_version_version_no"} <= _constraint_names(
        "quote_version"
    )
    assert _fk("quote_version", "quote_id").ondelete == "RESTRICT"  # history is never deleted
    assert "ix_quote_version_changed_by" in _index_names("quote_version")
    assert "updated_at" not in table.c  # history rows are never updated


def test_relationships_use_lazy_raise() -> None:
    rels = {
        f"{model.__name__}.{name}": rel
        for model in (Quote, QuoteAddon, QuoteVersion)
        for name, rel in model.__mapper__.relationships.items()
    }
    assert set(rels) == {
        "Quote.customer",
        "Quote.plan",
        "Quote.addons",
        "Quote.versions",
        "QuoteAddon.quote",
        "QuoteAddon.addon",
        "QuoteVersion.quote",
    }
    assert all(r.lazy == "raise" for r in rels.values())


def test_quote_addons_follow_the_quote() -> None:
    cascade = Quote.__mapper__.relationships["addons"].cascade
    assert cascade.delete_orphan
