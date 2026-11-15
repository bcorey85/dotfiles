"""Checks for scripts/mcp_ledger: it registers `ledger mcp` as the user-scope MCP server `ledger`.

Every case runs the script with a fake `claude` and a fake `ledger` first on PATH, inside a temp dir, so the real
`claude mcp` and the real user config are never touched. The fake `claude` keeps its servers as files and logs each
call, one line per call with the arguments joined by `|`.

Script location: MCP_LEDGER_SCRIPT, defaulting to scripts/mcp_ledger in the tree these tests sit in.
"""

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(os.environ.get("MCP_LEDGER_SCRIPT") or REPO_ROOT / "scripts" / "mcp_ledger")
SYSTEM_PATH = "/usr/bin:/bin"
USER_SCOPE = "User config (available in all your projects)"
PROJECT_SCOPE = "Project config (shared via .mcp.json)"

FAKE_CLAUDE = """#!/usr/bin/env bash
# Servers live as files in $FAKE_CLAUDE_STATE/servers; every call is logged.
state="$FAKE_CLAUDE_STATE"
( IFS='|'; echo "$*" >> "$state/calls.log" )
[ "$1" = mcp ] || exit 2
action="$2"
name="$3"
server_file="$state/servers/$name"
case "$action" in
  get)
    error_for="$FAKE_CLAUDE_GET_ERROR_FOR"
    if [ -n "$FAKE_CLAUDE_GET_ERROR" ] && { [ -z "$error_for" ] || [ "$error_for" = "$name" ]; }; then
      echo "$FAKE_CLAUDE_GET_ERROR"
      exit 2
    fi
    if [ -f "$server_file" ]; then
      echo "$name:"
      cat "$server_file"
      exit 0
    fi
    echo "No MCP server named \\"$name\\". Configured servers: other"
    exit 1
    ;;
  add)
    shift 3
    while [ "$1" != "--" ]; do shift; done
    shift
    scope_line="User config (available in all your projects)"
    printf '  Scope: %s\\n  Command: %s\\n  Args: %s\\n' "$scope_line" "$1" "$2" > "$server_file"
    ;;
  remove)
    rm "$server_file"
    ;;
  *) exit 2 ;;
esac
"""

FAKE_LEDGER = "#!/usr/bin/env bash\nexit 0\n"


class McpLedgerCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.bin_dir = self.root / "bin"
        self.state = self.root / "state"
        (self.state / "servers").mkdir(parents=True)
        self.bin_dir.mkdir()
        self.extra_path = []
        self.ledger_bin = None

    def install_fake(self, directory, name, text):
        directory.mkdir(parents=True, exist_ok=True)
        fake = directory / name
        fake.write_text(text)
        fake.chmod(0o755)
        return fake

    def install_claude(self):
        self.install_fake(self.bin_dir, "claude", FAKE_CLAUDE)

    def install_ledger(self, directory=None):
        directory = directory or self.bin_dir
        self.ledger_bin = self.install_fake(directory, "ledger", FAKE_LEDGER)
        if directory != self.bin_dir:
            self.extra_path.append(str(directory))

    def seed(self, name, command, args="mcp", scope=USER_SCOPE):
        text = f"  Scope: {scope}\n  Status: Connected\n  Command: {command}\n  Args: {args}\n"
        (self.state / "servers" / name).write_text(text)

    def has_server(self, name):
        return (self.state / "servers" / name).exists()

    def server_text(self, name):
        return (self.state / "servers" / name).read_text()

    def calls(self):
        log = self.state / "calls.log"
        if not log.exists():
            return []
        return log.read_text().splitlines()

    def changing_calls(self):
        return [call for call in self.calls() if call.startswith(("mcp|add|", "mcp|remove|"))]

    def run_script(self, **extra_env):
        search_path = ":".join([str(self.bin_dir), *self.extra_path, SYSTEM_PATH])
        env = {"PATH": search_path, "HOME": str(self.root), "FAKE_CLAUDE_STATE": str(self.state), **extra_env}
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False)


class RegisterTests(McpLedgerCase):
    def setUp(self):
        super().setUp()
        self.install_claude()
        self.install_ledger()

    def test_not_registered_adds_ledger_with_full_path(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"mcp|add|ledger|--scope|user|--|{self.ledger_bin}|mcp", self.calls())
        self.assertIn("Scope: User config", self.server_text("ledger"))

    def test_second_run_changes_nothing(self):
        self.run_script()
        changes_after_first = self.changing_calls()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.changing_calls(), changes_after_first)

    def test_hand_registered_bare_command_is_not_added_again(self):
        self.seed("ledger", "ledger")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("already registered", result.stdout)
        self.assertEqual(self.changing_calls(), [])

    def test_full_path_command_is_not_added_again(self):
        self.seed("ledger", str(self.ledger_bin))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("already registered", result.stdout)
        self.assertEqual(self.changing_calls(), [])

    def test_trailing_whitespace_in_fields_still_counts_as_registered(self):
        self.seed("ledger", "ledger   ", args="mcp \t")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.changing_calls(), [])

    def test_non_user_scope_is_reported_and_left_alone(self):
        self.seed("ledger", "ledger", scope=PROJECT_SCOPE)
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mcp_ledger: ledger is registered in project scope", result.stdout)
        self.assertEqual(self.changing_calls(), [])

    def test_user_entry_that_runs_something_else_is_replaced(self):
        self.seed("ledger", "/opt/other-server")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = [
            "mcp|remove|ledger|--scope|user",
            f"mcp|add|ledger|--scope|user|--|{self.ledger_bin}|mcp",
        ]
        self.assertEqual(self.changing_calls(), expected)

    def test_user_entry_with_other_args_is_replaced(self):
        self.seed("ledger", "ledger", args="serve")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mcp|remove|ledger|--scope|user", self.calls())
        self.assertIn(f"Command: {self.ledger_bin}", self.server_text("ledger"))

    def test_unknown_get_error_stops_before_any_change(self):
        result = self.run_script(FAKE_CLAUDE_GET_ERROR="boom: config unreadable")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mcp_ledger: claude mcp get failed", result.stdout)
        self.assertEqual(self.changing_calls(), [])


class OldNameTests(McpLedgerCase):
    def setUp(self):
        super().setUp()
        self.install_claude()
        self.install_ledger()

    def test_old_entry_with_full_path_is_removed_and_ledger_added(self):
        self.seed("agent-memory", str(self.ledger_bin))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.has_server("agent-memory"))
        self.assertTrue(self.has_server("ledger"))
        self.assertIn("removed old agent-memory entry", result.stdout)

    def test_old_entry_with_bare_command_is_removed(self):
        self.seed("agent-memory", "ledger")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.has_server("agent-memory"))

    def test_old_entry_is_removed_when_ledger_is_already_registered(self):
        self.seed("ledger", "ledger")
        self.seed("agent-memory", str(self.ledger_bin))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.changing_calls(), ["mcp|remove|agent-memory|--scope|user"])

    def test_old_entry_is_kept_when_ledger_registration_fails(self):
        self.seed("agent-memory", str(self.ledger_bin))
        result = self.run_script(FAKE_CLAUDE_GET_ERROR="boom", FAKE_CLAUDE_GET_ERROR_FOR="ledger")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.has_server("agent-memory"))

    def test_old_entry_for_another_command_is_left_alone_and_said_so(self):
        self.seed("agent-memory", "/opt/other-server", args="serve")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has_server("agent-memory"))
        self.assertIn("agent-memory does not run ledger mcp in user scope, left alone", result.stdout)
        self.assertTrue(self.has_server("ledger"))

    def test_old_entry_in_another_scope_is_left_alone(self):
        self.seed("agent-memory", "ledger", scope=PROJECT_SCOPE)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has_server("agent-memory"))
        self.assertIn("left alone", result.stdout)

    def test_unknown_error_reading_old_entry_fails_after_ledger_is_registered(self):
        result = self.run_script(FAKE_CLAUDE_GET_ERROR="boom", FAKE_CLAUDE_GET_ERROR_FOR="agent-memory")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mcp_ledger: claude mcp get agent-memory failed", result.stdout)
        self.assertTrue(self.has_server("ledger"))


class MissingProgramTests(McpLedgerCase):
    def setUp(self):
        super().setUp()
        if shutil.which("ledger", path=SYSTEM_PATH) or shutil.which("claude", path=SYSTEM_PATH):
            self.skipTest("ledger or claude is on the system path, so a missing one cannot be staged")

    def test_missing_ledger_exits_quietly_without_calling_claude(self):
        self.install_claude()
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertEqual(self.calls(), [])

    def test_missing_claude_fails_with_the_get_failure_message(self):
        self.install_ledger()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mcp_ledger: claude mcp get failed", result.stdout)


class PathWithSpacesTests(McpLedgerCase):
    def setUp(self):
        super().setUp()
        self.install_claude()
        self.install_ledger(self.root / "dir with space")

    def test_path_with_spaces_is_added_as_one_argument(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"mcp|add|ledger|--scope|user|--|{self.ledger_bin}|mcp", self.calls())

    def test_path_with_spaces_counts_as_registered(self):
        self.seed("ledger", str(self.ledger_bin))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.changing_calls(), [])


if __name__ == "__main__":
    unittest.main()
