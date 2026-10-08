# syntax=docker/dockerfile:1

# base: Python + a non-root user, shared by every stage.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# builder: install runtime packages into /app/.venv with uv.
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
# Packages first (cached layer), then our code.
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

# dev: + dev tools, autoreload; compose mounts ./src over /app/src.
FROM builder AS dev
RUN uv sync --frozen
COPY alembic.ini ./
USER app
EXPOSE 8000
CMD ["uvicorn", "policydesk.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# prod: only the venv + code, no uv, no dev tools.
FROM base AS prod
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY alembic.ini ./
USER app
EXPOSE 8000
CMD ["uvicorn", "policydesk.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
