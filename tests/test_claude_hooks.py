import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude/hooks"
# Built by joining, so this file itself never holds a secret-looking value.
FAKE_LIVE_KEY = "sk_live_" + "a1" * 12
FAKE_WEBHOOK_SECRET = "whsec_" + "b2" * 12


def run_hook(name: str, event: dict[str, Any], env: dict[str, str] | None = None) -> str | None:
    """Run one hook; return its permission decision, or None when it stays silent."""
    event.setdefault("cwd", str(ROOT))
    result = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    if not result.stdout.strip():
        return None
    decision: str = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    return decision


def tool(name: str, **tool_input: Any) -> dict[str, Any]:
    return {"tool_name": name, "tool_input": tool_input}


@pytest.mark.parametrize("path", [".env", "C:\\repo\\.env.local", "certs/server.pem", "secrets/x"])
def test_secret_files_are_denied(path: str) -> None:
    assert run_hook("guard_secrets.py", tool("Read", file_path=path)) == "deny"


@pytest.mark.parametrize("path", [".env.example", ".env.test", "src/policydesk/main.py"])
def test_normal_files_pass(path: str) -> None:
    assert run_hook("guard_secrets.py", tool("Edit", file_path=path, new_string="x = 1")) is None


@pytest.mark.parametrize("command", ["cat .env", "git add .env", "type C:\\repo\\.env.prod"])
def test_bash_touching_secret_files_is_denied(command: str) -> None:
    assert run_hook("guard_secrets.py", tool("Bash", command=command)) == "deny"


@pytest.mark.parametrize("command", ["cat .env.example", "just test", 'git commit -m "fix .env"'])
def test_normal_bash_passes(command: str) -> None:
    assert run_hook("guard_secrets.py", tool("Bash", command=command)) is None


@pytest.mark.parametrize("value", [FAKE_LIVE_KEY, FAKE_WEBHOOK_SECRET])
def test_writing_a_secret_value_is_denied(value: str) -> None:
    event = tool("Write", file_path="src/x.py", content=f'KEY = "{value}"')
    assert run_hook("guard_secrets.py", event) == "deny"


def test_placeholder_secret_passes() -> None:
    event = tool("Write", file_path="src/x.py", content='KEY = "sk_test_change_me"')
    assert run_hook("guard_secrets.py", event) is None


def test_committed_migration_asks() -> None:
    path = "src/policydesk/core/db/alembic/versions/20261003_0000-0001_base_tables.py"
    assert run_hook("guard_migrations.py", tool("Edit", file_path=path)) == "ask"


def test_new_migration_passes() -> None:
    path = "src/policydesk/core/db/alembic/versions/20991231_0000-9999_new.py"
    assert run_hook("guard_migrations.py", tool("Write", file_path=path)) is None


def test_migrate_against_prod_is_denied(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ENVIRONMENT=prod\n", encoding="utf-8")
    event = tool("Bash", command="uv run alembic upgrade head") | {"cwd": str(tmp_path)}
    assert run_hook("guard_prod.py", event, env=_env_without("ENVIRONMENT", "DB__HOST")) == "deny"


@pytest.mark.parametrize(
    "command", ["DB__HOST=prod-db just migrate", "cd x && uv run alembic upgrade head # prod"]
)
def test_prod_word_in_command_is_denied(command: str) -> None:
    assert run_hook("guard_prod.py", tool("Bash", command=command)) == "deny"


@pytest.mark.parametrize(
    "command",
    ["echo 'just migrate on prod'", "python - <<'EOF'\njust migrate prod\nEOF"],
)
def test_text_that_only_mentions_migrate_passes(command: str) -> None:
    assert run_hook("guard_prod.py", tool("Bash", command=command)) is None


def test_local_migrate_passes(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ENVIRONMENT=local\n", encoding="utf-8")
    event = tool("Bash", command="just migrate") | {"cwd": str(tmp_path)}
    assert run_hook("guard_prod.py", event, env=_env_without("ENVIRONMENT", "DB__HOST")) is None


def test_stop_hook_never_loops() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOKS / "on_stop.py")],
        input=json.dumps({"stop_hook_active": True, "cwd": str(ROOT)}),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""


def _env_without(*keys: str) -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in keys}
