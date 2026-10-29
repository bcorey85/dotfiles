"""Checks the metrics switch scripts telemetry_enabled.sh and telemetry_enabled.py behave the same.

The switch is the CLAUDE_TOOLKIT_TELEMETRY variable alone. Every case runs the script as a subprocess with HOME set
to a temp dir. Script location: TELEMETRY_ENABLED_DIR names the directory that holds both scripts. Unset, the
files under claude/.claude/scripts in this tree are used.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT_DIR = pathlib.Path(os.environ.get("TELEMETRY_ENABLED_DIR") or toolkit_paths.TELEMETRY_DIR)

PYTHON_RUNNER = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from telemetry_enabled import telemetry_enabled; "
    "sys.exit(0 if telemetry_enabled() else 1)"
)


class SwitchCases:
    """Cases shared by both implementations; a subclass supplies switch_command."""

    def setUp(self):
        temp_root = tempfile.TemporaryDirectory()
        self.addCleanup(temp_root.cleanup)
        self.home = pathlib.Path(temp_root.name).resolve() / "home"
        self.round_folder = self.home / "dev" / "evals" / "round-1"
        self.round_folder.mkdir(parents=True)
        (self.home / ".claude").mkdir()

    def is_on(self, setting=None, project_folder=None, file_present=False):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_PROJECT_DIR")}
        environment["HOME"] = str(self.home)
        if setting is not None:
            environment["CLAUDE_TOOLKIT_TELEMETRY"] = setting
        if project_folder is not None:
            environment["CLAUDE_PROJECT_DIR"] = str(project_folder)
        if file_present:
            (self.home / ".claude" / "toolkit-telemetry").touch()
        finished = subprocess.run(self.switch_command(), env=environment, cwd=str(self.home),
                                  capture_output=True, text=True)
        self.assertEqual(finished.stderr, "")
        self.assertIn(finished.returncode, (0, 1))
        return finished.returncode == 0

    def test_only_the_variable_set_to_one_turns_it_on(self):
        # The switch file is created last: it stays in the home for the cases after it, and never turns the switch on.
        cases = [
            ("no variable", {}, False),
            ("variable one", {"setting": "1"}, True),
            ("variable zero", {"setting": "0"}, False),
            ("variable one inside the evals folder", {"setting": "1", "project_folder": self.round_folder}, True),
            ("variable empty", {"setting": ""}, False),
            ("file alone", {"file_present": True}, False),
            ("variable zero with file", {"setting": "0", "file_present": True}, False),
            ("variable true with file", {"setting": "true", "file_present": True}, False),
        ]
        for name, options, expected in cases:
            with self.subTest(name):
                self.assertEqual(self.is_on(**options), expected)


class ShellSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [str(SCRIPT_DIR / "telemetry_enabled.sh")]


class PythonSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [sys.executable, "-I", "-c", PYTHON_RUNNER, str(SCRIPT_DIR)]


if __name__ == "__main__":
    unittest.main()
