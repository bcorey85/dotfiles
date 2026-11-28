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


def run_command(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command, "description": "d"}})
    return subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True, env=env)


class RgPathGateTest(unittest.TestCase):
    def assert_denied(self, command, fixed):
        finished = run_command(command)
        self.assertEqual(finished.returncode, 0)
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", decision)
        self.assertTrue(decision["permissionDecisionReason"].startswith("[rg-path-gate] "))
        self.assertIn(f"Run this instead: {fixed}", decision["permissionDecisionReason"])

    def assert_passes(self, command):
        finished = run_command(command)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")

    def test_a_one_step_call_with_no_path_is_allowed_with_the_dot_path_appended(self):
        cases = [
            ("rg foo", "rg foo ."),
            ("rg 'foo bar'", "rg 'foo bar' ."),
            # Leading whitespace stays; only the trailing whitespace is replaced by " .".
            ("  rg foo  \n", "  rg foo ."),
            ("rg foo -g '*.py'", "rg foo -g '*.py' ."),
            ("rg -e pat", "rg -e pat ."),
            ("rg -A3 foo", "rg -A3 foo ."),
            ("rg -e a -e b", "rg -e a -e b ."),
            ("rg -ie pat", "rg -ie pat ."),
            ("rg -t py foo", "rg -t py foo ."),
            ("rg --regexp pat", "rg --regexp pat ."),
            ("rg --glob='*.py' foo", "rg --glob='*.py' foo ."),
            ("rg -- -foo", "rg -- -foo ."),
            # A backslash-escaped `$` in double quotes is literal, so nothing expands.
            ('rg "a\\$b"', 'rg "a\\$b" .'),
        ]
        for command, updated in cases:
            with self.subTest(command=command):
                finished = run_command(command)
                self.assertEqual(finished.returncode, 0)
                decision = json.loads(finished.stdout)["hookSpecificOutput"]
                self.assertEqual(decision["hookEventName"], "PreToolUse")
                self.assertEqual(decision["permissionDecision"], "allow")
                self.assertEqual(decision["updatedInput"], {"command": updated, "description": "d"})

    def test_a_one_step_call_the_permission_rule_does_not_cover_is_denied_with_the_fixed_command(self):
        cases = [
            # A one-step call keeps its raw text, so `$X` and the brace list mean the same in the fixed command.
            ('rg "$X"', 'rg "$X" .'),
            ('rg "${X:=\\$(touch x)}${(e)X}"', 'rg "${X:=\\$(touch x)}${(e)X}" .'),
            ('rg "$(touch x)"', 'rg "$(touch x)" .'),
            ("rg ~foo", "rg ~foo ."),
            ("PATH=/x rg foo", "PATH=/x rg foo ."),
            ("FOO=1 rg foo", "FOO=1 rg foo ."),
            ("/tmp/x/rg foo", "/tmp/x/rg foo ."),
            ("rg $X", "rg $X ."),
            # Single quotes inside double quotes are literal, so the `$` still expands.
            ("rg \"'$X'\"", "rg \"'$X'\" ."),
            ("rg 'a\\'$X", "rg 'a\\'$X ."),
            ("rg {a,b}", "rg {a,b} ."),
            ("rg foo{a,b}", "rg foo{a,b} ."),
            ("rg =ls", "rg =ls ."),
            ("rg x*", "rg x* ."),
            ("rg `id`", "rg `id` ."),
            ('rg "`id`"', 'rg "`id`" .'),
            # A quoted part glued to more text is one double-quoted word, so the `$(...)` and backtick inside run.
            ("rg a\"b '$(touch x)' c\"d", "rg a\"b '$(touch x)' c\"d ."),
            ("rg a\"b '`id`' c\"d", "rg a\"b '`id`' c\"d ."),
            # The raw parser cannot read `\"`, so the call is denied, not left to crash the gate.
            ("rg \"\\\"'$(id)'\"", "rg \"\\\"'$(id)'\" ."),
            ("rg foo 2>&1", "rg foo ."),
            ("rg foo 2>/dev/null", "rg foo ."),
        ]
        for command, fixed in cases:
            with self.subTest(command=command):
                self.assert_denied(command, fixed)

    def test_a_dollar_inside_single_quotes_is_allowed(self):
        finished = run_command("rg 'foo$'")
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "allow")
        self.assertEqual(decision["updatedInput"]["command"], "rg 'foo$' .")

    def test_a_call_with_no_path_is_denied_with_the_fixed_command(self):
        cases = [
            ("rg foo && ls", "rg foo ."),
            ("rg foo | head", "rg foo ."),
            ("cd /tmp && rg foo", "rg foo ."),
            ("ls && \\\nrg foo", "rg foo ."),
            ('echo "$(ls | wc -l)"; rg foo', "rg foo ."),
            ("(rg foo)", "rg foo ."),
            ("rg foo 2>", "rg foo ."),
            ("rg foo # note", "rg foo ."),
            ("rg foo;", "rg foo ."),
            ("rg foo &", "rg foo ."),
            ("rg foo\nls", "rg foo ."),
            ("rg foo\nrg bar", "rg foo ."),
            ("'rg' foo", "'rg' foo ."),
            ('"rg" foo', '"rg" foo .'),
            ("\\rg foo", "\\rg foo ."),
            ("rg foo > out.txt", "rg foo ."),
            ("rg foo >> out.txt", "rg foo ."),
        ]
        for command, fixed in cases:
            with self.subTest(command=command):
                self.assert_denied(command, fixed)

    def test_a_dangling_option_is_denied_with_no_fixed_command(self):
        for command in ["rg foo -g", "rg -e", "rg foo -g && ls", "cd /tmp && rg foo -g", "rg", "rg -t py", "rg -i"]:
            with self.subTest(command=command):
                finished = run_command(command)
                self.assertEqual(finished.returncode, 0)
                decision = json.loads(finished.stdout)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertNotIn("Run this instead", decision["permissionDecisionReason"])
                self.assertIn("Pass the path.", decision["permissionDecisionReason"])

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
        env = dict(os.environ, CLAUDE_SKIP_HOOKS="1")
        finished = run_command("rg foo", env=env)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_a_malformed_payload_is_reported_on_stderr_and_does_not_block(self):
        finished = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))
        self.assertIn("rg_path_gate: crashed, call allowed unchecked", finished.stderr)


if __name__ == "__main__":
    unittest.main()
