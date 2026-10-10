"""Stop: when Python files changed, run query-count tests + the rules reviewer; block on failure."""

import json
import subprocess
import sys
from pathlib import Path

from _hooklib import project_root, read_event

NO_TESTS_COLLECTED = 5
MAX_REPORT = 3000


def changed_py_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    files = [line[3:].strip().strip('"') for line in out.splitlines() if not line.startswith(" D")]
    return [f for f in files if f.endswith(".py") and Path(root, f).is_file()]


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["uv", "run", "--no-sync", *args]
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)


def main() -> None:
    event = read_event()
    if event.get("stop_hook_active"):  # we already blocked once this turn: never loop
        sys.exit(0)
    root = project_root(event)
    files = changed_py_files(root)
    if not files:
        sys.exit(0)

    problems: list[str] = []
    tests = run(root, "pytest", "-m", "query_count", "-q", "-p", "no:cacheprovider")
    if tests.returncode not in (0, NO_TESTS_COLLECTED):
        problems.append("Query-count tests failed:\n" + tests.stdout[-MAX_REPORT:])

    if (root / "scripts/review_rules.py").is_file():
        review = run(root, "python", "scripts/review_rules.py", "--format", "text", *files)
        if review.returncode != 0:
            problems.append("Rules review found errors:\n" + review.stdout[-MAX_REPORT:])

    if problems:
        reason = "\n\n".join(problems) + "\n\nFix these before you finish."
        print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
