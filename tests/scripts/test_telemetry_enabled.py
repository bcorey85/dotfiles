"""Checks the metrics switch scripts telemetry_enabled.sh and telemetry_enabled.py behave the same.

Every case runs the script as a subprocess with HOME set to a temp dir, so no case reads the real switch file or
the real ~/dev/evals. Script location: TELEMETRY_ENABLED_DIR names the directory that holds both scripts. Unset,
the installed files under ~/.claude/scripts are used.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT_DIR = pathlib.Path(os.environ.get("TELEMETRY_ENABLED_DIR") or toolkit_paths.SCRIPTS_DIR)

PYTHON_RUNNER = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from telemetry_enabled import telemetry_enabled; "
    "sys.exit(0 if telemetry_enabled() else 1)"
)


class SwitchCases:
    """Cases shared by both implementations; a subclass supplies run_switch."""

    def setUp(self):
        temp_root = tempfile.TemporaryDirectory()
        self.addCleanup(temp_root.cleanup)
        self.root = pathlib.Path(temp_root.name).resolve()
        self.home = self.root / "home"
        self.home_in_environment = self.home
        self.evals_folder = self.home / "dev" / "evals"
        self.round_folder = self.evals_folder / "round-1"
        self.sibling_folder = self.home / "dev" / "evals-old" / "round-1"
        self.other_folder = self.home / "work" / "repo"
        for folder in (self.round_folder, self.sibling_folder, self.other_folder, self.home / ".claude"):
            folder.mkdir(parents=True)

    def environment(self, setting, project_folder):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_PROJECT_DIR")}
        environment["HOME"] = str(self.home_in_environment)
        if setting is not None:
            environment["CLAUDE_TOOLKIT_TELEMETRY"] = setting
        if project_folder is not None:
            environment["CLAUDE_PROJECT_DIR"] = str(project_folder)
        return environment

    def switch_file(self, present):
        switch_file = self.home / ".claude" / "toolkit-telemetry"
        if present:
            switch_file.touch()
        else:
            switch_file.unlink(missing_ok=True)

    def is_on(self, setting=None, project_folder=None, cwd=None, file_present=False, delete_cwd=False):
        self.switch_file(file_present)
        command = self.switch_command()
        if delete_cwd:
            # Start the switch from a current folder that was deleted after the shell entered it.
            command = ["bash", "-c", 'mkdir gone && cd gone && rmdir ../gone && exec "$@"', "bash", *command]
        finished = subprocess.run(command, env=self.environment(setting, project_folder),
                                  cwd=str(cwd or self.other_folder), capture_output=True, text=True)
        self.assertNotIn("Traceback", finished.stderr)
        if not delete_cwd:
            self.assertEqual(finished.stderr, "")
        self.assertIn(finished.returncode, (0, 1))
        return finished.returncode == 0

    def test_off_with_no_variable_and_no_file(self):
        self.assertFalse(self.is_on())

    def test_on_with_variable_one(self):
        self.assertTrue(self.is_on(setting="1"))

    def test_on_with_file(self):
        self.assertTrue(self.is_on(file_present=True))

    def test_variable_zero_is_off_even_with_file(self):
        self.assertFalse(self.is_on(setting="0", file_present=True))

    def test_variable_zero_is_off_with_project_folder_outside_evals(self):
        self.assertFalse(self.is_on(setting="0", project_folder=self.other_folder, file_present=True))

    def test_file_inside_evals_project_folder_is_off(self):
        self.assertFalse(self.is_on(project_folder=self.round_folder, file_present=True))

    def test_evals_folder_itself_is_inside(self):
        self.assertFalse(self.is_on(project_folder=self.evals_folder, file_present=True))

    def test_variable_one_inside_evals_is_on(self):
        self.assertTrue(self.is_on(setting="1", project_folder=self.round_folder))

    def test_variable_zero_inside_evals_is_off(self):
        self.assertFalse(self.is_on(setting="0", project_folder=self.round_folder, file_present=True))

    def test_evals_old_is_not_inside_evals(self):
        self.assertTrue(self.is_on(project_folder=self.sibling_folder, file_present=True))

    def test_symlink_into_evals_is_inside(self):
        link = self.root / "link-to-round"
        link.symlink_to(self.round_folder)
        self.assertFalse(self.is_on(project_folder=link, file_present=True))

    def test_symlink_out_of_evals_is_not_inside(self):
        link = self.evals_folder / "link-to-repo"
        link.symlink_to(self.other_folder)
        self.assertTrue(self.is_on(project_folder=link, file_present=True))

    def test_current_folder_inside_evals_is_off_when_project_variable_unset(self):
        self.assertFalse(self.is_on(cwd=self.round_folder, file_present=True))

    def test_project_variable_wins_over_current_folder(self):
        self.assertTrue(self.is_on(project_folder=self.other_folder, cwd=self.round_folder, file_present=True))

    def test_project_folder_outside_evals_with_file_is_on(self):
        self.assertTrue(self.is_on(project_folder=self.other_folder, file_present=True))

    def test_project_folder_outside_evals_without_file_is_off(self):
        self.assertFalse(self.is_on(project_folder=self.other_folder))

    def test_empty_project_variable_falls_back_to_current_folder_inside_evals(self):
        self.assertFalse(self.is_on(project_folder="", cwd=self.round_folder, file_present=True))

    def test_empty_project_variable_falls_back_to_current_folder_outside_evals(self):
        self.assertTrue(self.is_on(project_folder="", cwd=self.other_folder, file_present=True))

    def test_missing_project_folder_inside_evals_is_off(self):
        self.assertFalse(self.is_on(project_folder=self.evals_folder / "not-made-yet", file_present=True))

    def test_missing_project_folder_outside_evals_is_on(self):
        self.assertTrue(self.is_on(project_folder=self.other_folder / "not-made-yet", file_present=True))

    def test_missing_relative_project_folder_is_outside_evals(self):
        self.assertTrue(self.is_on(project_folder="not-made-yet", cwd=self.round_folder, file_present=True))

    def test_dot_dot_through_missing_folder_into_evals_is_off(self):
        project_folder = f"{self.evals_folder}/not-made-yet/../round-1"
        self.assertFalse(self.is_on(project_folder=project_folder, file_present=True))

    def test_missing_project_folder_under_symlinked_evals_folder(self):
        # The evals folder resolves to its real path and the missing folder stays as given, so they do not match.
        self.evals_folder.rename(self.home / "dev" / "real-evals")
        self.evals_folder.symlink_to(self.home / "dev" / "real-evals")
        self.assertTrue(self.is_on(project_folder=self.evals_folder / "not-made-yet", file_present=True))

    def test_missing_project_folder_under_symlinked_home(self):
        home_link = self.root / "home-link"
        home_link.symlink_to(self.home)
        self.home_in_environment = home_link
        self.assertTrue(self.is_on(project_folder=home_link / "dev" / "evals" / "not-made-yet", file_present=True))

    def test_existing_project_folder_under_symlinked_home_is_inside(self):
        home_link = self.root / "home-link"
        home_link.symlink_to(self.home)
        self.home_in_environment = home_link
        self.assertFalse(self.is_on(project_folder=home_link / "dev" / "evals" / "round-1", file_present=True))

    def test_symlinked_evals_folder_holds_inside_projects(self):
        real_evals = self.home / "dev" / "real-evals"
        self.evals_folder.rename(real_evals)
        self.evals_folder.symlink_to(real_evals)
        self.assertFalse(self.is_on(project_folder=self.evals_folder / "round-1", file_present=True))
        self.assertFalse(self.is_on(project_folder=real_evals / "round-1", file_present=True))
        self.assertFalse(self.is_on(project_folder=self.evals_folder, file_present=True))
        self.assertTrue(self.is_on(project_folder=self.sibling_folder, file_present=True))

    def test_trailing_slash_inside_evals_is_off(self):
        self.assertFalse(self.is_on(project_folder=f"{self.round_folder}/", file_present=True))

    def test_trailing_slash_outside_evals_is_on(self):
        self.assertTrue(self.is_on(project_folder=f"{self.sibling_folder}/", file_present=True))

    def test_trailing_slash_on_missing_folder_inside_evals_is_off(self):
        self.assertFalse(self.is_on(project_folder=f"{self.evals_folder}/not-made-yet/", file_present=True))

    def test_other_variable_value_is_not_a_switch(self):
        self.assertFalse(self.is_on(setting="true"))
        self.assertTrue(self.is_on(setting="true", file_present=True))
        self.assertFalse(self.is_on(setting="true", project_folder=self.round_folder, file_present=True))

    def test_empty_variable_is_not_a_switch(self):
        self.assertFalse(self.is_on(setting=""))
        self.assertTrue(self.is_on(setting="", file_present=True))

    def test_deleted_current_folder_with_relative_project_variable_does_not_crash(self):
        self.assertTrue(self.is_on(project_folder="repo", file_present=True, delete_cwd=True))

    def test_deleted_current_folder_counts_as_outside_evals(self):
        self.assertTrue(self.is_on(cwd=self.round_folder, file_present=True, delete_cwd=True))


class ShellSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [str(SCRIPT_DIR / "telemetry_enabled.sh")]


class PythonSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [sys.executable, "-I", "-c", PYTHON_RUNNER, str(SCRIPT_DIR)]


if __name__ == "__main__":
    unittest.main()
