import importlib
import os
import pathlib
import shutil
import subprocess
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
