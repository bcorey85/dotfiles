import importlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths


class ToolkitPathsTest(unittest.TestCase):
    def tearDown(self):
        importlib.reload(toolkit_paths)

    def reload_with_environment(self, **environment):
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("TOOLKIT_CLAUDE_DIR", None)
            os.environ.update(environment)
            return importlib.reload(toolkit_paths)

    def test_the_default_is_the_toolkit_folder_of_the_tree_the_tests_sit_in(self):
        tree_claude_dir = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"

        reloaded = self.reload_with_environment()

        self.assertEqual(tree_claude_dir, reloaded.CLAUDE_DIR)
        self.assertEqual(tree_claude_dir / "scripts", reloaded.SCRIPTS_DIR)

    def test_the_environment_variable_points_the_tests_at_another_folder(self):
        reloaded = self.reload_with_environment(TOOLKIT_CLAUDE_DIR="/somewhere/else/.claude")

        self.assertEqual(pathlib.Path("/somewhere/else/.claude"), reloaded.CLAUDE_DIR)
        self.assertEqual(pathlib.Path("/somewhere/else/.claude/scripts"), reloaded.SCRIPTS_DIR)

    def test_an_empty_environment_variable_falls_back_to_the_tree_folder(self):
        tree_claude_dir = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"

        reloaded = self.reload_with_environment(TOOLKIT_CLAUDE_DIR="")

        self.assertEqual(tree_claude_dir, reloaded.CLAUDE_DIR)

    def test_the_scripts_folder_holds_the_shared_script_utilities(self):
        self.assertTrue((toolkit_paths.LIB_DIR / "script_utils.py").is_file())

    def test_each_script_folder_sits_under_the_scripts_folder(self):
        reloaded = self.reload_with_environment(TOOLKIT_CLAUDE_DIR="/somewhere/else/.claude")

        self.assertEqual(
            {name: pathlib.Path("/somewhere/else/.claude/scripts") / name
             for name in ("code", "review", "telemetry", "lib", "tools", "gates")},
            {"code": reloaded.CODE_DIR, "review": reloaded.REVIEW_DIR, "telemetry": reloaded.TELEMETRY_DIR,
             "lib": reloaded.LIB_DIR, "tools": reloaded.TOOLS_DIR, "gates": reloaded.GATES_DIR},
        )


class FirstPythonThatStartsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.shims = pathlib.Path(folder.name)

    def plant(self, name, body):
        shim = self.shims / name
        shim.write_text(f"#!/bin/sh\n{body}\n")
        shim.chmod(0o755)

    def first_started(self, names):
        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.shims)}):
            return toolkit_paths.first_python_that_starts(names)

    def test_a_shim_that_cannot_start_is_passed_over(self):
        # The shape a version manager leaves behind: on PATH, exit 1, a message on stderr.
        self.plant("python3.12", "echo 'mise ERROR python3.12 is not a valid shim' >&2; exit 1")

        self.assertIsNone(self.first_started(("python3.13", "python3.12", "python3.11")))

    def test_the_next_name_is_used_when_an_earlier_one_cannot_start(self):
        self.plant("python3.13", "exit 1")
        self.plant("python3.12", f'exec "{sys.executable}" "$@"')

        started = self.first_started(("python3.13", "python3.12"))

        self.assertEqual(sys.executable, started)

    def test_no_name_on_the_search_path_gives_none(self):
        self.assertIsNone(self.first_started(("python3.13",)))


class RealLedgerGuardTest(unittest.TestCase):
    def test_a_test_that_plants_no_stand_in_reaches_only_the_failing_guard(self):
        guard_folder = pathlib.Path(os.environ[toolkit_paths.LEDGER_GUARD_VARIABLE])

        found_ledger = shutil.which("ledger")
        write = subprocess.run(["ledger", "write", "review_run"], input="{}", capture_output=True, text=True)

        self.assertEqual(str(guard_folder / "ledger"), found_ledger)
        self.assertEqual(toolkit_paths.LEDGER_GUARD_EXIT, write.returncode)
        self.assertIn("a test reached the real ledger", write.stderr)
        self.assertFalse((pathlib.Path(os.environ["CARGO_HOME"]) / "bin" / "ledger").exists())

    def test_a_reload_keeps_the_one_guard(self):
        guard_folder = os.environ[toolkit_paths.LEDGER_GUARD_VARIABLE]
        path_before = os.environ["PATH"]

        importlib.reload(toolkit_paths)

        self.assertEqual(guard_folder, os.environ[toolkit_paths.LEDGER_GUARD_VARIABLE])
        self.assertEqual(path_before, os.environ["PATH"])
        self.assertTrue(pathlib.Path(guard_folder, "ledger").is_file())


if __name__ == "__main__":
    unittest.main()
