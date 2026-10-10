"""PreToolUse: never read, write or stage secret files; never write secret values."""

import re
import shlex
import sys
from typing import Any

from _hooklib import as_posix, decide, read_event

SAFE_ENV_FILES = {".env.example", ".env.test"}
SECRET_FILE = re.compile(
    r"(^|/)(\.env(\.[\w.-]+)?|[^/]*\.(pem|key|p12|pfx)|id_(rsa|ecdsa|ed25519)[^/]*)$"
)
SECRET_DIR = re.compile(r"(^|/)secrets(/|$)")
# Placeholders like sk_test_change_me are fine; real-looking keys are not.
SECRET_VALUE = re.compile(
    r"sk_live_[0-9A-Za-z]{8,}"
    r"|(?:sk|rk)_test_(?!change_me)[0-9A-Za-z]{16,}"
    r"|whsec_(?!change_me)[0-9A-Za-z]{16,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def is_secret_path(path: str) -> bool:
    path = as_posix(path.strip("'\""))
    if path.rsplit("/", 1)[-1] in SAFE_ENV_FILES:
        return False
    return bool(SECRET_FILE.search(path) or SECRET_DIR.search(path))


def bash_tokens(command: str) -> list[str]:
    """shlex handles quotes but eats Windows backslashes, so check the plain split too."""
    try:
        quoted = shlex.split(command, posix=True)
    except ValueError:
        quoted = []
    return quoted + [t for t in command.split() if "\\" in t]


def written_text(tool_input: dict[str, Any]) -> str:
    parts = [tool_input.get("content"), tool_input.get("new_string"), tool_input.get("new_source")]
    parts += [e.get("new_string") for e in tool_input.get("edits") or []]
    return "\n".join(p for p in parts if isinstance(p, str))


def main() -> None:
    event = read_event()
    tool = event.get("tool_name", "")
    tool_input: dict[str, Any] = event.get("tool_input") or {}

    if tool == "Bash":
        for token in bash_tokens(tool_input.get("command", "")):
            for piece in re.split(r"[=<>|;&]", token):
                if piece and is_secret_path(piece):
                    decide("deny", f"Blocked: the command touches a secret file ({piece}).")
        sys.exit(0)

    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    if isinstance(path, str) and is_secret_path(path):
        decide("deny", f"Blocked: {path} is a secret file. Use .env.example for examples.")

    if SECRET_VALUE.search(written_text(tool_input)):
        decide("deny", "Blocked: the new text contains a secret value (API key or private key).")


if __name__ == "__main__":
    main()
