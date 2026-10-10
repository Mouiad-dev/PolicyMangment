"""PreToolUse: never run migrations against a prod database."""

import os
import re
import sys
from pathlib import Path

from _hooklib import decide, project_root, read_event

# A migrate command at the start of a shell segment, maybe after KEY=value and `uv run`.
MIGRATE = re.compile(
    r"(?:^|[;&|(\n])\s*(?:\w+=\S*\s+)*(?:uv\s+run\s+(?:--\S+\s+)*)?"
    r"(?:alembic\s+(?:upgrade|downgrade|stamp)|just\s+(?:migrate|downgrade))\b"
)
PROD_WORD = re.compile(r"\bprod(uction)?\b", re.IGNORECASE)


def env_file_value(root: Path, key: str) -> str:
    """Read one key from .env without printing anything else."""
    env = root / ".env"
    if not env.is_file():
        return ""
    for line in env.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == key:
            return value.split("#", 1)[0].strip().strip("'\"")
    return ""


def main() -> None:
    event = read_event()
    command = (event.get("tool_input") or {}).get("command", "")
    command = command.split("<<", 1)[0]  # heredoc bodies are text, not commands
    if not MIGRATE.search(command):
        sys.exit(0)
    root = project_root(event)
    environment = os.environ.get("ENVIRONMENT") or env_file_value(root, "ENVIRONMENT")
    db_host = os.environ.get("DB__HOST") or env_file_value(root, "DB__HOST")
    if PROD_WORD.search(command) or environment == "prod" or PROD_WORD.search(db_host):
        decide("deny", "Blocked: migrations never run against prod from Claude. Ask Mouiad.")


if __name__ == "__main__":
    main()
