import json
from textwrap import dedent

import pytest
from scripts.review_rules import (
    Finding,
    load_metadata,
    report,
    review,
    review_schema,
    review_source,
    summary_markdown,
)
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    Table,
)

MOD = "src/policydesk/modules/demo/"


def rules_hit(path: str, code: str) -> set[str]:
    return {f.rule for f in review_source(path, dedent(code))}


@pytest.mark.parametrize(
    ("path", "bad", "good", "rule"),
    [
        (
            MOD + "endpoints.py",
            "from sqlalchemy.ext.asyncio import AsyncSession\n",
            "from policydesk.modules.demo.service import DemoService\n",
            "PD001",
        ),
        (MOD + "service.py", "async def f(s):\n    await s.commit()\n", "x = 1\n", "PD002"),
        (
            MOD + "models.py",
            "class A:\n    price: Mapped[float | None]\n",
            "class A:\n    price: Mapped[Decimal]\n",
            "PD003",
        ),
        (MOD + "models.py", "import stripe\n", "from decimal import Decimal\n", "PD007"),
        (MOD + "repository.py", "e = create_async_engine(url)\n", "x = 1\n", "PD008"),
        (
            MOD + "repository.py",
            "m = async_sessionmaker(engine)\n",
            "m = async_sessionmaker(engine, expire_on_commit=False)\n",
            "PD008",
        ),
        (
            MOD + "models.py",
            "plans = relationship(back_populates='product')\n",
            "plans = relationship(back_populates='product', lazy='raise')\n",
            "PD010",
        ),
        (
            MOD + "service.py",
            "@lru_cache\ndef hasher(settings: Settings): ...\n",
            "def hasher(settings: Settings): ...\n",
            "PD011",
        ),
        (
            MOD + "service.py",
            'def f():\n    """One.\n\n    Two.\n    Three."""\n',
            'def f():\n    """One.\n\n    Two."""\n',
            "PD012",
        ),
        (MOD + "service.py", "# a\n# b\n# c\nx = 1\n", "# a\n# b\nx = 1\n", "PD012"),
    ],
)
def test_code_rule_catches_bad_and_passes_good(path: str, bad: str, good: str, rule: str) -> None:
    assert rule in rules_hit(path, bad)
    assert rule not in rules_hit(path, good)


def test_engine_is_allowed_in_session_module() -> None:
    path = "src/policydesk/core/db/session.py"
    assert "PD008" not in rules_hit(path, "e = create_async_engine(url)\n")


def test_files_outside_src_are_ignored() -> None:
    assert rules_hit("tests/test_x.py", "import stripe\nawait s.commit()\n") == set()


def _schema(*tables: Table) -> set[str]:
    return {f.rule for f in review_schema(tables[0].metadata)}


def test_fk_without_index_is_caught() -> None:
    md = MetaData(naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s"})
    Table("parent", md, Column("id", BigInteger, primary_key=True))
    child = Table(
        "child",
        md,
        Column("id", BigInteger, primary_key=True),
        Column("parent_id", ForeignKey("parent.id")),
    )
    assert "PD004" in _schema(child)
    Index("ix_child_parent_id", child.c.parent_id)
    assert "PD004" not in _schema(child)


def test_badly_named_constraint_is_caught() -> None:
    md = MetaData()
    t = Table("t", md, Column("id", BigInteger, primary_key=True), CheckConstraint("id > 0", "pos"))
    assert "PD005" in _schema(t)


def test_money_rules() -> None:
    md = MetaData(naming_convention={"ck": "ck_%(table_name)s_%(constraint_name)s"})
    Table(
        "invoice",
        md,
        Column("id", BigInteger, primary_key=True),
        Column("total", Numeric(10, 2)),
        Column("fee", Numeric(12, 2)),
        CheckConstraint("fee >= 0", name="fee_non_negative"),
    )
    messages = {f.message for f in review_schema(md) if f.rule == "PD006"}
    assert messages == {"invoice.total is not NUMERIC(12,2)", "invoice.total has no CHECK >= 0"}


def test_signed_money_columns_need_no_check() -> None:
    md = MetaData()
    Table(
        "commission",
        md,
        Column("id", BigInteger, primary_key=True),
        Column("amount", Numeric(12, 2)),
    )
    assert not [f for f in review_schema(md) if f.rule == "PD006"]


def test_current_project_schema_is_clean() -> None:
    assert [f for f in review_schema(load_metadata()) if f.severity == "error"] == []


def test_current_project_has_no_errors() -> None:
    findings = review(["src/policydesk/main.py"], base="HEAD", metadata=None)
    assert [f for f in findings if f.severity == "error"] == []


def _finding() -> Finding:
    return Finding("PD002", "error", MOD + "service.py", 3, "service calls .commit()", "w", "f")


def test_json_report_is_structured() -> None:
    data = json.loads(report([_finding()], "json"))
    assert data["summary"] == {"errors": 1, "warnings": 0, "passed": False}
    assert data["findings"][0]["rule"] == "PD002"
    assert set(data["findings"][0]) == {"rule", "severity", "file", "line", "message", "why", "fix"}


def test_github_report_makes_annotations() -> None:
    first_line = report([_finding()], "github").splitlines()[0]
    assert first_line.startswith(f"::error file={MOD}service.py,line=3,title=PD002::")


def test_summary_markdown_has_a_table() -> None:
    assert "| error | PD002 |" in summary_markdown([_finding()])
    assert "passed" in summary_markdown([])
