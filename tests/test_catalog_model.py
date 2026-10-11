from sqlalchemy import ForeignKey

from policydesk.core.db.base import Base
from policydesk.modules.catalogs.models import Addon, Plan, Product, Rate, Setting


def _fk(table: str, column: str) -> ForeignKey:
    (fk,) = Base.metadata.tables[table].c[column].foreign_keys
    return fk


def _constraint_names(table: str) -> set[str]:
    return {str(c.name) for c in Base.metadata.tables[table].constraints}


def _index_names(table: str) -> set[str | None]:
    return {i.name for i in Base.metadata.tables[table].indexes}


def test_constraint_names_follow_srs() -> None:
    assert {"pk_product", "ck_product_code", "uq_product_code"} <= _constraint_names("product")
    assert {"pk_plan", "uq_plan_product_id_code"} <= _constraint_names("plan")
    assert {
        "pk_addon",
        "uq_addon_product_id_code",
        "ck_addon_price_non_negative",
    } <= _constraint_names("addon")
    assert {
        "pk_rate",
        "uq_rate_plan_id_band_valid_from",
        "ck_rate_base_price_non_negative",
    } <= _constraint_names("rate")
    assert {"pk_setting", "ck_setting_value_type"} <= _constraint_names("setting")


def test_foreign_keys_point_up_and_restrict() -> None:
    for table, column, target in [
        ("plan", "product_id", "product.id"),
        ("addon", "product_id", "product.id"),
        ("rate", "plan_id", "plan.id"),
        ("rate", "created_by", "user_account.id"),
        ("setting", "updated_by", "user_account.id"),
    ]:
        fk = _fk(table, column)
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"


def test_fk_columns_have_index() -> None:
    assert "ix_plan_product_id" in _index_names("plan")
    assert "ix_addon_product_id" in _index_names("addon")
    assert {"ix_rate_plan_id", "ix_rate_created_by"} <= _index_names("rate")
    assert "ix_setting_updated_by" in _index_names("setting")


def test_fk_columns_are_not_unique() -> None:
    # unique=True on a parent FK would turn one-to-many into one-to-one.
    for table, column in [("plan", "product_id"), ("addon", "product_id"), ("rate", "plan_id")]:
        assert not Base.metadata.tables[table].c[column].unique


def test_money_columns_are_numeric_12_2() -> None:
    for table, column in [("addon", "price"), ("rate", "base_price")]:
        col_type = Base.metadata.tables[table].c[column].type
        assert (col_type.precision, col_type.scale) == (12, 2)  # type: ignore[attr-defined]


def test_rate_is_never_updated() -> None:
    columns = Base.metadata.tables["rate"].c
    assert "created_at" in columns
    assert "updated_at" not in columns


def test_setting_key_is_primary_key() -> None:
    assert [c.name for c in Base.metadata.tables["setting"].primary_key] == ["key"]


def test_relationships_use_lazy_raise() -> None:
    rels = {
        f"{model.__name__}.{name}": rel
        for model in (Product, Plan, Addon, Rate, Setting)
        for name, rel in model.__mapper__.relationships.items()
    }
    assert set(rels) == {
        "Product.plans",
        "Product.addons",
        "Plan.product",
        "Plan.rates",
        "Addon.product",
        "Rate.plan",
    }
    assert all(r.lazy == "raise" for r in rels.values())


def test_product_and_plans_stay_in_sync() -> None:
    car = Product(code="CAR", name="Car insurance")
    plan = Plan(code="COMPREHENSIVE", name="Comprehensive")
    car.plans.append(plan)
    assert plan.product is car
