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

    def test_the_default_is_the_installed_claude_folder(self):
        reloaded = self.reload_with_environment()

        self.assertEqual(pathlib.Path.home() / ".claude", reloaded.CLAUDE_DIR)
        self.assertEqual(pathlib.Path.home() / ".claude" / "scripts", reloaded.SCRIPTS_DIR)

    def test_the_environment_variable_points_the_tests_at_another_folder(self):
        reloaded = self.reload_with_environment(TOOLKIT_CLAUDE_DIR="/somewhere/else/.claude")

        self.assertEqual(pathlib.Path("/somewhere/else/.claude"), reloaded.CLAUDE_DIR)
        self.assertEqual(pathlib.Path("/somewhere/else/.claude/scripts"), reloaded.SCRIPTS_DIR)

    def test_an_empty_environment_variable_falls_back_to_the_installed_folder(self):
        reloaded = self.reload_with_environment(TOOLKIT_CLAUDE_DIR="")

        self.assertEqual(pathlib.Path.home() / ".claude", reloaded.CLAUDE_DIR)

    def test_the_scripts_folder_holds_the_shared_script_utilities(self):
        self.assertTrue((toolkit_paths.SCRIPTS_DIR / "script_utils.py").is_file())


if __name__ == "__main__":
    unittest.main()
