"""Small helpers shared by the Claude Code hooks (stdlib only)."""

import json
import sys
from pathlib import Path
from typing import Any, Literal, NoReturn

Decision = Literal["allow", "deny", "ask"]


def read_event() -> dict[str, Any]:
    data: dict[str, Any] = json.load(sys.stdin)
    return data


def decide(decision: Decision, reason: str) -> NoReturn:
    """Answer a PreToolUse event and exit."""
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def project_root(event: dict[str, Any]) -> Path:
    return Path(event.get("cwd") or ".").resolve()


def as_posix(path: str) -> str:
    return path.replace("\\", "/")
