---
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
---

# Testing rules and definition of done

## Definition of done for every step
- Tests written first for services; all tests pass (`just test`).
- `ruff check`, `ruff format --check`, `mypy --strict` pass (`just check`), and `just review` is clean.
- For DB changes: one reviewed Alembic migration, `alembic upgrade head` and `alembic check` pass.
- No N+1: a `@pytest.mark.query_count` test where lists or detail pages load related data.
- `docs/PROGRESS.md` updated and Mouiad's check question answered.

## How we test
- Service unit tests use `FakeUnitOfWork` (no DB). Integration tests use real Postgres (`db_session`:
  migrate once, outer transaction + savepoint per test, rolled back at the end).
- API tests use the `client` fixture (httpx `AsyncClient` + `get_session` override).
- `filterwarnings = error`: fix warnings at the source, do not ignore them.
- Never put a real-looking secret in a test; build fake keys by joining strings.
- The Claude Stop hook runs `pytest -m query_count` when Python files changed.
