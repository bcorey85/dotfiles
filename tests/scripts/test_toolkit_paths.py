import importlib
import os
import pathlib
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


if __name__ == "__main__":
    unittest.main()
