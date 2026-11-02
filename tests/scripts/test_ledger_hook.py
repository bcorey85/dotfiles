"""Checks for ledger-hook, the wrapper a settings.json hook runs in place of an inline `ledger hook` call.

Every case runs with HOME and CARGO_HOME set to a temp dir and a PATH that holds no ledger unless the case plants one.
"""

import json
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

# A stand-in ledger that records its arguments and stdin, then exits with LEDGER_HOOK_EXIT.
HOOK_LEDGER_SOURCE = """#!/usr/bin/env bash
printf '%s\\n' "$*" > "$LEDGER_HOOK_CALL"
cat >> "$LEDGER_HOOK_CALL"
exit "${LEDGER_HOOK_EXIT:-0}"
"""


class LedgerHookTest(unittest.TestCase):
    """ledger-hook runs `ledger hook <event>` with the event on stdin, and never fails the hook."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.call_path = self.temp_root / "ledger-call.txt"

    def plant_ledger(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        ledger_path = folder / "ledger"
        ledger_path.write_text(HOOK_LEDGER_SOURCE)
        ledger_path.chmod(0o755)

    def run_hook(self, extra_path="", ledger_exit="0", hook_event="stop", stdin='{"event":"Stop"}', telemetry=None):
        bare_path = fake_ledger.path_without_ledger(os.environ["PATH"])
        env = {
            **os.environ,
            "HOME": str(self.home),
            "CARGO_HOME": str(self.home / ".cargo"),
            "PATH": f"{extra_path}:{bare_path}" if extra_path else bare_path,
            "LEDGER_HOOK_CALL": str(self.call_path),
            "LEDGER_HOOK_EXIT": ledger_exit,
        }
        env.pop("CLAUDE_TOOLKIT_TELEMETRY", None)
        env.pop("CLAUDE_SKIP_HOOKS", None)
        env.pop("SKILL_USAGE_FILE", None)
        if telemetry:
            env["CLAUDE_TOOLKIT_TELEMETRY"] = telemetry
        hook_script = toolkit_paths.TELEMETRY_DIR / "ledger-hook"
        return subprocess.run(
            [str(hook_script), hook_event], env=env, capture_output=True, text=True, input=stdin
        )

    def rows(self, file_name):
        log_file = self.home / ".claude" / file_name
        return [json.loads(line) for line in log_file.read_text().splitlines()]

    def test_no_ledger_keeps_a_skill_tool_call_in_the_skill_usage_file(self):
        event = {"hook_event_name": "PostToolUse", "tool_input": {"skill": "review"}}

        done = self.run_hook(hook_event="skill-use", stdin=json.dumps(event), telemetry="1")

        self.assertEqual((done.returncode, done.stderr), (0, ""))
        [row] = self.rows("skill-usage.jsonl")
        self.assertEqual((row["skill"], row["via"], set(row)), ("review", "model", {"ts", "skill", "via", "repo"}))

    def test_no_ledger_keeps_a_slash_prompt_as_a_user_skill_row(self):
        event = {"hook_event_name": "UserPromptSubmit", "prompt": "/code do the thing"}

        self.run_hook(hook_event="skill-use", stdin=json.dumps(event), telemetry="1")

        [row] = self.rows("skill-usage.jsonl")
        self.assertEqual((row["skill"], row["via"]), ("code", "user"))

    def test_no_ledger_keeps_a_test_file_edit_with_its_snippet_cut_to_200(self):
        event = {
            "tool_name": "Edit",
            "agent_type": "coder",
            "tool_input": {"file_path": "/repo/tests/test_a.py", "new_string": "x" * 300},
        }

        done = self.run_hook(hook_event="test-edit", stdin=json.dumps(event), telemetry="1")

        self.assertEqual((done.returncode, done.stderr), (0, ""))
        [row] = self.rows("test-edit-telemetry.jsonl")
        self.assertEqual((row["tool"], row["agent"], row["file"]), ("Edit", "coder", "/repo/tests/test_a.py"))
        self.assertEqual(row["snippet"], "x" * 200)

    def test_an_edit_to_a_source_file_writes_no_row(self):
        event = {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/a.py", "new_string": "x"}}

        self.run_hook(hook_event="test-edit", stdin=json.dumps(event), telemetry="1")

        self.assertFalse((self.home / ".claude" / "test-edit-telemetry.jsonl").exists())

    def test_the_switch_off_writes_no_row(self):
        event = {"hook_event_name": "PostToolUse", "tool_input": {"skill": "review"}}

        self.run_hook(hook_event="skill-use", stdin=json.dumps(event))

        self.assertFalse((self.home / ".claude" / "skill-usage.jsonl").exists())

    def test_a_ledger_on_path_takes_the_event_and_no_row_goes_to_the_file(self):
        on_path = self.temp_root / "on-path"
        self.plant_ledger(on_path)
        event = {"hook_event_name": "PostToolUse", "tool_input": {"skill": "review"}}

        self.run_hook(extra_path=str(on_path), hook_event="skill-use", stdin=json.dumps(event), telemetry="1")

        self.assertTrue(self.call_path.read_text().startswith("hook skill-use\n"))
        self.assertFalse((self.home / ".claude" / "skill-usage.jsonl").exists())

    def test_a_bad_event_exits_0_with_one_stderr_line(self):
        done = self.run_hook(hook_event="skill-use", stdin="not json", telemetry="1")

        self.assertEqual(done.returncode, 0)
        self.assertIn("hook_local_row: skill-use row dropped", done.stderr)

    def test_the_ledger_on_path_gets_the_event_and_its_stdin(self):
        on_path = self.temp_root / "on-path"
        self.plant_ledger(on_path)

        done = self.run_hook(extra_path=str(on_path))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.call_path.read_text(), 'hook stop\n{"event":"Stop"}')

    def test_a_ledger_in_the_cargo_bin_folder_runs_when_path_has_none(self):
        self.plant_ledger(self.home / ".cargo" / "bin")

        done = self.run_hook()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.call_path.read_text().startswith("hook stop\n"))

    def test_a_failing_ledger_still_exits_0(self):
        self.plant_ledger(self.home / ".cargo" / "bin")

        done = self.run_hook(ledger_exit="3")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.call_path.exists(), "the ledger never ran")

    def test_no_ledger_exits_0_silently(self):
        done = self.run_hook()

        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertFalse(self.call_path.exists())

    def test_a_directory_named_ledger_in_the_cargo_bin_folder_is_not_run(self):
        (self.home / ".cargo" / "bin" / "ledger").mkdir(parents=True)

        done = self.run_hook()

        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertFalse(self.call_path.exists())


if __name__ == "__main__":
    unittest.main()
