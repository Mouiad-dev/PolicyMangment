from sqlalchemy import ForeignKey, inspect

from policydesk.core.db.base import Base
from policydesk.modules.customers.models import Address, Customer


def _fk(table: str, column: str) -> ForeignKey:
    (fk,) = Base.metadata.tables[table].c[column].foreign_keys
    return fk


def test_customer_constraint_names() -> None:
    names = {c.name for c in Base.metadata.tables["customer"].constraints}
    assert {
        "pk_customer",
        "ck_customer_id_type",
        "ck_customer_mykad_12_digits",
        "ck_customer_mobile_format",
        "uq_customer_id_type_id_number",
        "uq_customer_user_id",
        "fk_customer_user_id_user_account",
        "fk_customer_agent_id_user_account",
    } <= names


def test_address_constraint_names() -> None:
    names = {c.name for c in Base.metadata.tables["address"].constraints}
    assert {"pk_address", "ck_address_postcode_format", "fk_address_customer_id_customer"} <= names


def test_foreign_keys_point_up_and_restrict() -> None:
    for table, column, target in [
        ("customer", "user_id", "user_account.id"),
        ("customer", "agent_id", "user_account.id"),
        ("address", "customer_id", "customer.id"),
    ]:
        fk = _fk(table, column)
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"


def test_no_link_back_from_user_account_or_customer() -> None:
    assert "customer_id" not in Base.metadata.tables["user_account"].c
    assert "address_id" not in Base.metadata.tables["customer"].c


def test_fk_columns_have_index() -> None:
    customer = {i.name for i in Base.metadata.tables["customer"].indexes}
    address = {i.name for i in Base.metadata.tables["address"].indexes}
    assert "ix_customer_agent_id" in customer
    assert "ix_address_customer_id" in address


def test_relationships_use_lazy_raise() -> None:
    rels = {**inspect(Customer).relationships, **inspect(Address).relationships}
    assert set(rels) == {"addresses", "user", "agent", "customer"}
    assert all(r.lazy == "raise" for r in rels.values())


def test_user_and_agent_use_their_own_fk() -> None:
    rels = inspect(Customer).relationships
    assert [c.name for c in rels["user"].local_columns] == ["user_id"]
    assert [c.name for c in rels["agent"].local_columns] == ["agent_id"]


def test_addresses_and_customer_stay_in_sync() -> None:
    customer = Customer(full_name="Ali bin Ahmad")
    address = Address(line1="1 Jalan Ampang", city="Kuala Lumpur", postcode="50450", state="WP")
    customer.addresses.append(address)
    assert address.customer is customer
