---
paths:
  - "**/*.py"
---

# FastAPI + app rules (PolicyDesk)

## Stack
Python 3.13, **uv**, FastAPI, **SQLAlchemy 2.0 async + asyncpg**, Alembic, **PostgreSQL 16**, pytest +
pytest-asyncio, httpx `AsyncClient`, ruff, mypy `--strict`, pre-commit, Docker Compose.

## Layers
- `endpoints` (thin) → `uow-> service` (business logic) → `repository` (data access) → `models`.
- An endpoint calls **one** service method and returns the result. It never touches `AsyncSession`.
- A service never calls `commit()`; the **Unit of Work** commits or rolls back.
- Read-only screens may use **selectors**: plain functions that return DTOs, not ORM objects.
- Every module uses the same file names: `models.py dtos.py endpoints.py repository.py service.py
  dependencies.py exceptions.py`.

## Async and runtime
- One engine per process (made in lifespan, kept in app state); `engine.dispose()` on shutdown.
- `expire_on_commit=False` on every session.
- Never call Stripe / SMTP / any network inside an open DB transaction.
- Errors: raise an `AppError` subclass; handlers turn it into one error shape. Unknown errors = 500, no stack.
- Domain events go to the outbox **in the same transaction**; handlers are idempotent (`processed_event`).
- Secrets only come from env / Settings. Never write a real key in code, tests or docs.

## fastapi-orderly: ideas only, never copied
Reference: https://github.com/HHHMHA/fastapi-orderly — learn the layout and ideas, write every file fresh.
Do better where it is weak: `lru_cache` on a function that takes `Settings` → make the object once at
start-up; no dead code; pool sizing + Postgres timeouts; `/health/live` + `/health/ready`; request logging
on; only services we use; error handling + Unit of Work.

## Automatic checks
- `scripts/review_rules.py` (rules PD001–PD012) runs in CI, on PRs, and in the Claude Stop hook.
- `just review` checks the whole repo; `just review-diff` checks only changed files.
