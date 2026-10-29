"""Checks for rg_path_gate.py, the PreToolUse hook that denies an `rg` call with no path and no piped input.

Set RG_PATH_GATE_SCRIPT to run against another copy, such as a staged one."""
import json
import os
import pathlib
import subprocess
import sys
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("RG_PATH_GATE_SCRIPT") or toolkit_paths.GATES_DIR / "rg_path_gate.py")


def run_command(command):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True)


class RgPathGateTest(unittest.TestCase):
    def assert_denied(self, command, fixed):
        finished = run_command(command)
        self.assertEqual(finished.returncode, 0)
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", decision)
        self.assertIn(f"Run this instead: {fixed}", decision["permissionDecisionReason"])

    def assert_passes(self, command):
        finished = run_command(command)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")

    def test_a_call_with_no_path_and_no_piped_input_is_denied_with_the_fixed_command(self):
        cases = [
            ("rg foo", "rg foo ."),
            ("rg 'foo bar'", "rg 'foo bar' ."),
            ("rg foo | head", "rg foo ."),
            ("cd /tmp && rg foo", "rg foo ."),
            ("rg foo -g '*.py'", "rg foo -g '*.py' ."),
            ("rg -e pat", "rg -e pat ."),
            ("rg --regexp pat", "rg --regexp pat ."),
            ("rg -e a -e b", "rg -e a -e b ."),
            ("rg -A3 foo", "rg -A3 foo ."),
            ("rg -ie pat", "rg -ie pat ."),
            ("rg --glob=*.py foo", "rg '--glob=*.py' foo ."),
            ("rg -t py foo", "rg -t py foo ."),
            ("rg -- -foo", "rg -- -foo ."),
            ('echo "$(ls | wc -l)"; rg foo', "rg foo ."),
        ]
        for command, fixed in cases:
            with self.subTest(command=command):
                self.assert_denied(command, fixed)

    def test_a_call_with_a_path_or_input_or_no_rg_command_passes(self):
        commands = [
            "rg foo src/",
            "rg foo .",
            "cat file | rg foo",
            "git log | rg foo | head",
            "rg foo < file.txt",
            "rg foo <<< 'some text'",
            "rg --files",
            "rg --files -g '*.py'",
            "rg foo -g '*.py' src",
            "rg -e pat src",
            "rg -ie pat src",
            "rg -t py foo lib",
            "rg -- -foo src",
            "rg foo -",
            "grep foo",
            "echo rg foo",
            "cat merge.txt",
            "gh pr create --title t --body \"$(cat <<'EOF'\n## Test plan\nrg -n pattern\nEOF\n)\"",
            "echo \"$(cat <<'EOF'\nrg foo\nEOF\n)\"",
            "rg 'foo",
            "",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assert_passes(command)

    def test_skip_hooks_env_passes(self):
        payload = json.dumps({"tool_input": {"command": "rg foo"}})
        env = dict(os.environ, CLAUDE_SKIP_HOOKS="1")
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True,
                                  env=env)
        self.assertEqual(finished.stdout, "")

    def test_malformed_payload_passes(self):
        finished = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
