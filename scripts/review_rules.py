"""PolicyDesk rules reviewer: checks our FastAPI + SQLAlchemy rules and prints structured findings.

Usage: python scripts/review_rules.py [FILES...] [--format text|json|github] [--base REF]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Literal

from sqlalchemy import CheckConstraint, MetaData, Numeric
from sqlalchemy.schema import (
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = "src/policydesk/"
MIGRATIONS = "src/policydesk/core/db/alembic/versions/"
SCHEMA_FILE = "src/policydesk/core/db/registry.py"
Severity = Literal["error", "warning"]
REPORT_VERSION = 1
# Known, accepted exceptions: (rule, file) -> reason. Keep this list short and explained.
EXCEPTIONS: dict[tuple[str, str], str] = {
    ("PD001", "src/policydesk/modules/health/endpoints.py"): "readiness probe runs SELECT 1 itself",
}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    file: str
    line: int
    message: str
    why: str
    fix: str


class Rule:
    """One rule = one Strategy. Code rules read a file's AST; schema rules read Base.metadata."""

    id: str
    severity: Severity
    why: str
    fix: str

    def finding(self, file: str, line: int, message: str) -> Finding:
        return Finding(self.id, self.severity, file, line, message, self.why, self.fix)


class CodeRule(Rule):
    def applies(self, path: str) -> bool:
        return path.startswith(SRC) and not path.startswith(MIGRATIONS)

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        raise NotImplementedError


class SchemaRule(Rule):
    def check(self, metadata: MetaData) -> Iterator[Finding]:
        raise NotImplementedError


# ---------- helpers ----------


def imported_names(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield every imported module and name, e.g. 'sqlalchemy.ext.asyncio', 'AsyncSession'."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", node.lineno
            for alias in node.names:
                yield alias.name, node.lineno


def calls(tree: ast.Module) -> Iterator[tuple[ast.Call, str]]:
    """Yield each call with its simple function name (`x.commit()` -> 'commit')."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                yield node, func.attr
            elif isinstance(func, ast.Name):
                yield node, func.id


def keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def mentions(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


# ---------- code rules ----------


class ThinEndpoints(CodeRule):
    id, severity = "PD001", "error"
    why = "Endpoints are thin: one service call each. Only the Unit of Work owns the session."
    fix = "Move the DB work into a service + repository; inject the service, not AsyncSession."

    def applies(self, path: str) -> bool:
        return super().applies(path) and path.endswith("endpoints.py")

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for name, line in imported_names(tree):
            if name == "AsyncSession":
                yield self.finding(path, line, "endpoint imports AsyncSession")


class NoCommitInService(CodeRule):
    id, severity = "PD002", "error"
    why = "Services never commit; the Unit of Work commits once, so a command is all-or-nothing."
    fix = "Remove .commit(); let `async with uow:` + `await uow.commit()` in the UoW layer do it."

    def applies(self, path: str) -> bool:
        return super().applies(path) and path.endswith("service.py")

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for call, name in calls(tree):
            if name == "commit":
                yield self.finding(path, call.lineno, "service calls .commit()")


class NoFloatMoney(CodeRule):
    id, severity = "PD003", "error"
    why = "float cannot hold money exactly (0.1 + 0.2 != 0.3). Money is NUMERIC(12,2) + Decimal."
    fix = "Use Mapped[Decimal] (NUMERIC(12,2)) instead of float / Float."

    def applies(self, path: str) -> bool:
        return super().applies(path) and (path.endswith("models.py") or "/core/db/" in path)

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript) or not mentions(node.value, "Mapped"):
                continue
            if mentions(node.slice, "float"):
                yield self.finding(path, node.lineno, "Mapped[float] column")
        for name, line in imported_names(tree):
            if name == "Float":
                yield self.finding(path, line, "imports the Float column type")


class NoIntegrationsInModels(CodeRule):
    id, severity = "PD007", "error"
    why = "Models hold domain rules only; outside calls live behind ports (PaymentGateway, ...)."
    fix = "Move the call into an adapter in the module's service layer."
    banned: ClassVar[tuple[str, ...]] = ("stripe", "smtplib", "aiosmtplib", "httpx", "requests")

    def applies(self, path: str) -> bool:
        return super().applies(path) and path.endswith("models.py")

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for name, line in imported_names(tree):
            if name.split(".")[0] in self.banned:
                yield self.finding(path, line, f"model imports {name}")


class OneEngineSafeSessions(CodeRule):
    id, severity = "PD008", "error"
    why = "One engine per process (lifespan); expire_on_commit=False avoids MissingGreenlet."
    fix = "Create the engine only in core/db/session.py and pass expire_on_commit=False."
    engine_home = "src/policydesk/core/db/session.py"

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for call, name in calls(tree):
            if name == "create_async_engine" and path != self.engine_home:
                yield self.finding(
                    path, call.lineno, "create_async_engine outside core/db/session.py"
                )
            if name in ("async_sessionmaker", "AsyncSession"):
                value = keyword(call, "expire_on_commit")
                if not (isinstance(value, ast.Constant) and value.value is False):
                    yield self.finding(
                        path, call.lineno, f"{name}() without expire_on_commit=False"
                    )


class ExplicitLazy(CodeRule):
    id, severity = "PD010", "warning"
    why = "A default lazy load hides N+1 queries and fails in async (MissingGreenlet)."
    fix = 'Set lazy="raise" (or another strategy on purpose) and load with selectinload/joinedload.'

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for call, name in calls(tree):
            if name == "relationship" and keyword(call, "lazy") is None:
                yield self.finding(path, call.lineno, "relationship() without lazy=")


class NoCacheOnSettingsArg(CodeRule):
    id, severity = "PD011", "warning"
    why = "lru_cache needs hashable args; Settings is not, and the cache hides config bugs."
    fix = "Build the object once at start-up (lifespan) and keep it in app state."

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            cached = any(
                mentions(d, "lru_cache") or mentions(d, "cache") for d in node.decorator_list
            )
            takes_settings = any(
                a.annotation and mentions(a.annotation, "Settings") for a in node.args.args
            )
            if cached and takes_settings:
                yield self.finding(path, node.lineno, f"{node.name}() is cached and takes Settings")


class ShortComments(CodeRule):
    id, severity = "PD012", "warning"
    why = "Project rule: comments and docstrings are max 2 lines; the long story goes in chat/docs."
    fix = "Shorten it to 2 lines or remove it if the code is clear."
    max_lines = 2

    def check(self, path: str, tree: ast.Module, source: str) -> Iterator[Finding]:
        for node in ast.walk(tree):
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                doc = ast.get_docstring(node, clean=True)
                if doc and len([ln for ln in doc.splitlines() if ln.strip()]) > self.max_lines:
                    line = node.body[0].lineno if node.body else 1
                    yield self.finding(path, line, "docstring longer than 2 lines")
        run = 0
        for number, text in enumerate(source.splitlines(), start=1):
            run = run + 1 if text.strip().startswith("#") else 0
            if run == self.max_lines + 1:
                yield self.finding(
                    path, number - self.max_lines, "comment block longer than 2 lines"
                )


# ---------- schema rules (Base.metadata) ----------


class FkHasIndex(SchemaRule):
    id, severity = "PD004", "error"
    why = "Postgres does not index FK columns; joins and ON DELETE checks get slow (DATA-03)."
    fix = "Add index=True on the FK column, or an Index whose first columns are the FK columns."

    def check(self, metadata: MetaData) -> Iterator[Finding]:
        for table in metadata.sorted_tables:
            leading = [
                [c.name for c in obj.columns]
                for obj in [*table.indexes, *table.constraints]
                if isinstance(obj, Index | UniqueConstraint | PrimaryKeyConstraint)
            ]
            for fk in table.foreign_key_constraints:
                cols = [c.name for c in fk.columns]
                if not any(idx[: len(cols)] == cols for idx in leading):
                    yield self.finding(
                        SCHEMA_FILE, 1, f"{table.name}({', '.join(cols)}) has no index"
                    )


class NamedConstraints(SchemaRule):
    id, severity = "PD005", "error"
    why = "Stable names keep Alembic diffs clean and errors readable (DATA-02)."
    fix = "Name it with the prefix pattern, or rely on the naming convention on Base."
    prefixes: ClassVar[dict[type, tuple[str, ...]]] = {
        PrimaryKeyConstraint: ("pk_",),
        ForeignKeyConstraint: ("fk_",),
        UniqueConstraint: ("uq_",),
        CheckConstraint: ("ck_",),
    }

    def check(self, metadata: MetaData) -> Iterator[Finding]:
        for table in metadata.sorted_tables:
            for obj in [*table.constraints, *table.indexes]:
                expected = (
                    ("ux_", "uq_")
                    if isinstance(obj, Index) and obj.unique
                    else ("ix_",)
                    if isinstance(obj, Index)
                    else self.prefixes.get(type(obj), ())
                )
                raw_name = getattr(obj, "name", None)
                name = str(raw_name) if raw_name else ""
                if expected and not name.startswith(expected):
                    kind = type(obj).__name__
                    yield self.finding(
                        SCHEMA_FILE, 1, f"{table.name}: {kind} named {name!r}, expected {expected}"
                    )


class MoneyColumns(SchemaRule):
    id, severity = "PD006", "error"
    why = "Money is NUMERIC(12,2) with CHECK >= 0, except the two signed columns (DATA-04)."
    fix = "Use Numeric(12, 2) and add CheckConstraint('<col> >= 0', name='<col>_non_negative')."
    signed: ClassVar[set[str]] = {"endorsement.premium_diff", "commission.amount"}
    other_numeric: ClassVar[set[str]] = {"commission.rate"}  # NUMERIC(5,2) percent, not money

    def check(self, metadata: MetaData) -> Iterator[Finding]:
        for table in metadata.sorted_tables:
            checks = " ".join(
                str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
            )
            for col in table.columns:
                key = f"{table.name}.{col.name}"
                if not isinstance(col.type, Numeric) or key in self.other_numeric:
                    continue
                if (col.type.precision, col.type.scale) != (12, 2):
                    yield self.finding(SCHEMA_FILE, 1, f"{key} is not NUMERIC(12,2)")
                if key not in self.signed and not re.search(rf"\b{col.name}\s*>=?\s*0\b", checks):
                    yield self.finding(SCHEMA_FILE, 1, f"{key} has no CHECK >= 0")


# ---------- repo rule (git) ----------


class AppliedMigrationsUnchanged(Rule):
    id, severity = "PD009", "error"
    why = "A committed migration may already be applied; changing it splits databases apart."
    fix = "Revert the change and write a new migration instead."

    def check(self, base: str) -> Iterator[Finding]:
        out = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=MDR", base, "--", MIGRATIONS],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for path in out.split():
            yield self.finding(path, 1, f"migration changed or deleted compared to {base}")


CODE_RULES: list[CodeRule] = [
    ThinEndpoints(),
    NoCommitInService(),
    NoFloatMoney(),
    NoIntegrationsInModels(),
    OneEngineSafeSessions(),
    ExplicitLazy(),
    NoCacheOnSettingsArg(),
    ShortComments(),
]
SCHEMA_RULES: list[SchemaRule] = [FkHasIndex(), NamedConstraints(), MoneyColumns()]


# ---------- runner ----------


def review_source(path: str, source: str) -> list[Finding]:
    rules = [r for r in CODE_RULES if r.applies(path)]
    if not rules:
        return []
    tree = ast.parse(source, filename=path)
    return [f for rule in rules for f in rule.check(path, tree, source)]


def review_schema(metadata: MetaData) -> list[Finding]:
    return [f for rule in SCHEMA_RULES for f in rule.check(metadata)]


def load_metadata() -> MetaData:
    import policydesk.core.db.registry  # noqa: F401  (imports every model)
    from policydesk.core.db.base import Base

    return Base.metadata


def default_files() -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / SRC).rglob("*.py"))


def review(files: Iterable[str], base: str | None, metadata: MetaData | None) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        path = Path(file)
        rel = path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file
        rel = rel.replace("\\", "/")
        if rel.endswith(".py") and (ROOT / rel).is_file():
            findings += review_source(rel, (ROOT / rel).read_text(encoding="utf-8"))
    if metadata is not None:
        findings += review_schema(metadata)
    if base:
        findings += AppliedMigrationsUnchanged().check(base)
    findings = [f for f in findings if (f.rule, f.file) not in EXCEPTIONS]
    order = {"error": 0, "warning": 1}
    return sorted(findings, key=lambda f: (order[f.severity], f.file, f.line, f.rule))


def report(findings: Sequence[Finding], fmt: str) -> str:
    errors = sum(f.severity == "error" for f in findings)
    warnings = len(findings) - errors
    if fmt == "json":
        payload = {
            "version": REPORT_VERSION,
            "summary": {"errors": errors, "warnings": warnings, "passed": errors == 0},
            "findings": [asdict(f) for f in findings],
        }
        return json.dumps(payload, indent=2)
    if fmt == "github":
        lines = [
            f"::{f.severity} file={f.file},line={f.line},title={f.rule}::{f.message}. {f.fix}"
            for f in findings
        ]
        return "\n".join([*lines, f"{errors} error(s), {warnings} warning(s)"])
    lines = [
        f"{f.file}:{f.line}: {f.severity.upper()} {f.rule} {f.message}\n    why: {f.why}\n"
        f"    fix: {f.fix}"
        for f in findings
    ]
    return "\n".join([*lines, f"{errors} error(s), {warnings} warning(s)"])


def summary_markdown(findings: Sequence[Finding]) -> str:
    errors = sum(f.severity == "error" for f in findings)
    head = "## Rules review: " + ("passed" if errors == 0 else f"{errors} error(s)")
    if not findings:
        return head + "\n\nNo findings.\n"
    rows = [f"| {f.severity} | {f.rule} | `{f.file}:{f.line}` | {f.message} |" for f in findings]
    return "\n".join(
        [head, "", "| Severity | Rule | Where | Message |", "|---|---|---|---|", *rows, ""]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("files", nargs="*", help="files to check (default: all of src/)")
    parser.add_argument("--format", choices=["text", "json", "github"], default="text")
    parser.add_argument("--base", help="git ref; flags changed migrations (PD009)")
    parser.add_argument("--no-schema", action="store_true", help="skip Base.metadata rules")
    args = parser.parse_args(argv)

    metadata = None if args.no_schema else load_metadata()
    findings = review(args.files or default_files(), args.base, metadata)
    print(report(findings, args.format))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.format == "github" and summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(findings))
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
