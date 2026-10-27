"""Checks for warn_skip_hooks.py, the SessionStart hook that warns when CLAUDE_SKIP_HOOKS is set.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import subprocess
import sys
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "warn_skip_hooks.py"

EXPECTED = (
    '{"systemMessage":"\\n\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f\\nCLAUDE_SKIP_HOOKS is set \u2014 all CB Security '
    "Hooks are bypassed for this session.\\n\\nTo re-enable hooks, unset the variable and restart Claude "
    'Code:\\n  unset CLAUDE_SKIP_HOOKS\\n\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f"}\n'
)

PARITY_CASES = [
    {"name": "unset", "stdin": ""},
    {"name": "empty", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": ""}},
    {"name": "one", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": "1"}},
    {"name": "word", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": "false"}},
    {"name": "stdin ignored", "stdin": '{"hook_event_name":"SessionStart"}', "env": {"CLAUDE_SKIP_HOOKS": "x"}},
]
TYPICAL = {"name": "typical", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": "1"}}


def run_hook(skip=None, stdin=""):
    environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    if skip is not None:
        environment["CLAUDE_SKIP_HOOKS"] = skip
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin.encode("utf-8"), capture_output=True,
                          env=environment)


class WarnSkipHooksTest(unittest.TestCase):
    def test_unset_prints_nothing(self):
        finished = run_hook()
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, b"", b""))

    def test_empty_value_prints_nothing(self):
        self.assertEqual(run_hook(skip="").stdout, b"")

    def test_any_non_empty_value_prints_the_warning_exactly(self):
        for value in ("1", "false", "yes please"):
            finished = run_hook(skip=value)
            self.assertEqual(finished.returncode, 0)
            self.assertEqual(finished.stderr, b"")
            self.assertEqual(finished.stdout.decode("utf-8"), EXPECTED)

    def test_output_is_one_json_line_with_a_system_message(self):
        finished = run_hook(skip="1", stdin='{"hook_event_name":"SessionStart"}')
        self.assertEqual(finished.stdout.count(b"\n"), 1)
        message = json.loads(finished.stdout)["systemMessage"]
        self.assertTrue(message.startswith("\n"))
        self.assertIn("unset CLAUDE_SKIP_HOOKS", message)


if __name__ == "__main__":
    unittest.main()
