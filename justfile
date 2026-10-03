# PolicyDesk task runner. Run `just` to see all recipes.
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Show the list of recipes
default:
    @just --list

# Install all dependencies (creates/updates uv.lock)
install:
    uv sync

# Lint, format-check and type-check (our code only: src + tests)
check:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run mypy --strict src

# Run the tests
test:
    uv run pytest
