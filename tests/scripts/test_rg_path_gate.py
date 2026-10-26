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
SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"


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

    def test_no_path_is_denied_with_the_fixed_command(self):
        self.assert_denied("rg foo", "rg foo .")

    def test_no_path_with_quoted_pattern_keeps_the_quotes(self):
        self.assert_denied("rg 'foo bar'", "rg 'foo bar' .")

    def test_explicit_path_passes(self):
        self.assert_passes("rg foo src/")
        self.assert_passes("rg foo .")

    def test_rg_first_in_a_pipeline_is_denied(self):
        self.assert_denied("rg foo | head", "rg foo .")

    def test_rg_after_a_chain_operator_is_denied(self):
        self.assert_denied("cd /tmp && rg foo", "rg foo .")

    def test_piped_input_passes(self):
        self.assert_passes("cat file | rg foo")
        self.assert_passes("git log | rg foo | head")

    def test_input_redirection_passes(self):
        self.assert_passes("rg foo < file.txt")
        self.assert_passes("rg foo <<< 'some text'")

    def test_files_mode_passes(self):
        self.assert_passes("rg --files")
        self.assert_passes("rg --files -g '*.py'")

    def test_glob_flag_value_is_not_the_path(self):
        self.assert_denied("rg foo -g '*.py'", "rg foo -g '*.py' .")
        self.assert_passes("rg foo -g '*.py' src")

    def test_pattern_flag_value_is_the_pattern_not_a_path(self):
        self.assert_denied("rg -e pat", "rg -e pat .")
        self.assert_passes("rg -e pat src")
        self.assert_denied("rg --regexp pat", "rg --regexp pat .")

    def test_two_pattern_flags_without_path_is_denied(self):
        self.assert_denied("rg -e a -e b", "rg -e a -e b .")

    def test_attached_and_clustered_flag_values(self):
        self.assert_denied("rg -A3 foo", "rg -A3 foo .")
        self.assert_denied("rg -ie pat", "rg -ie pat .")
        self.assert_passes("rg -ie pat src")
        self.assert_denied("rg --glob=*.py foo", "rg '--glob=*.py' foo .")

    def test_flag_value_option_with_separate_word(self):
        self.assert_denied("rg -t py foo", "rg -t py foo .")
        self.assert_passes("rg -t py foo lib")

    def test_double_dash_then_pattern_is_denied_and_with_path_passes(self):
        self.assert_denied("rg -- -foo", "rg -- -foo .")
        self.assert_passes("rg -- -foo src")

    def test_stdin_dash_path_passes(self):
        self.assert_passes("rg foo -")

    def test_other_commands_and_rg_inside_words_pass(self):
        self.assert_passes("grep foo")
        self.assert_passes("echo rg foo")
        self.assert_passes("cat merge.txt")

    def test_unparseable_command_passes(self):
        self.assert_passes("rg 'foo")
        self.assert_passes("")

    def test_skip_hooks_env_passes(self):
        payload = json.dumps({"tool_input": {"command": "rg foo"}})
        env = dict(os.environ, CLAUDE_SKIP_HOOKS="1")
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True,
                                  env=env)
        self.assertEqual(finished.stdout, "")

    def test_malformed_payload_passes(self):
        finished = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_settings_registers_gate_with_an_rg_filter(self):
        groups = json.loads(SETTINGS.read_text())["hooks"]["PreToolUse"]
        handlers = [handler for group in groups if group.get("matcher") == "Bash" for handler in group["hooks"]
                    if handler["command"].endswith("gates/rg_path_gate.py")]
        self.assertEqual([handler.get("if") for handler in handlers], ["Bash(*rg*)"])


if __name__ == "__main__":
    unittest.main()
