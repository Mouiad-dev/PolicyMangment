"""PreToolUse: ask before changing a migration that is already committed (maybe applied)."""

import re
import subprocess
import sys
from pathlib import Path

from _hooklib import as_posix, decide, project_root, read_event

MIGRATION = re.compile(r"/alembic/versions/[^/]+\.py$")


def committed(root: Path, file: Path) -> bool:
    try:
        rel = as_posix(str(file.resolve().relative_to(root)))
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel}"], cwd=root, capture_output=True, check=False
    )
    return result.returncode == 0


def main() -> None:
    event = read_event()
    path = (event.get("tool_input") or {}).get("file_path")
    if not isinstance(path, str) or not MIGRATION.search(as_posix(path)):
        sys.exit(0)
    root = project_root(event)
    if committed(root, root / path):
        decide(
            "ask",
            f"{Path(path).name} is already committed, so it may be applied on a database. "
            "Write a NEW migration instead, unless Mouiad agrees to edit this one.",
        )


if __name__ == "__main__":
    main()
