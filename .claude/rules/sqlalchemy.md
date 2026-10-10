---
paths:
  - "src/**/models.py"
  - "src/**/repository.py"
  - "src/**/selectors.py"
  - "src/policydesk/core/db/**"
  - "**/alembic/**"
---

# SQLAlchemy + database rules (PolicyDesk)

## Models
- Models hold domain rules (`policy.can_cancel(on)`), never integrations (no Stripe, no email, no httpx).
- Shared columns come from mixins in `core/db/mixins.py` (no own `id` / `created_at`). Mixins before `Base`.
- Status changes live in one model method that checks an allowed-transitions map.

## Constraints (SRS DATA-02, DATA-03)
- Every FK, UNIQUE, NOT NULL and CHECK is defined and **named** (naming convention on `Base`).
- Prefixes: `pk_ fk_ uq_ ck_ ix_ ux_` (partial unique) + table + columns.
- **Every FK column has an index.** ON DELETE is RESTRICT unless the SRS says otherwise.

## Money (SRS DATA-04)
- `NUMERIC(12,2)` in the DB and `Decimal` in Python, round half up. **Never `float`.**
- Money columns have `CHECK (col >= 0)`, except `endorsement.premium_diff` and `commission.amount`.

## Queries and N+1
- Every query that returns related data sets `selectinload` / `joinedload` explicitly.
- Every `relationship()` sets `lazy=` on purpose (prefer `lazy="raise"`), so a hidden lazy load fails loudly.
- Lists and detail pages get a `@pytest.mark.query_count` test using the `sql_log` fixture.

## Migrations
- Every schema change is one reviewed Alembic migration (one per feature group).
- **Never edit a committed migration** — write a new one (a hook asks Mouiad first).
- `alembic upgrade head` + `alembic check` must pass. Never run migrations against prod.
