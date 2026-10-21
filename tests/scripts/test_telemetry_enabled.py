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

SCRIPT_DIR = pathlib.Path(os.environ.get("TELEMETRY_ENABLED_DIR") or pathlib.Path.home() / ".claude" / "scripts")

PYTHON_RUNNER = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from telemetry_enabled import telemetry_enabled; "
    "sys.exit(0 if telemetry_enabled() else 1)"
)


class SwitchCases:
    """Cases shared by both implementations; a subclass supplies run_switch."""

    def setUp(self):
        tempRoot = tempfile.TemporaryDirectory()
        self.addCleanup(tempRoot.cleanup)
        self.root = pathlib.Path(tempRoot.name).resolve()
        self.home = self.root / "home"
        self.homeInEnvironment = self.home
        self.evalsFolder = self.home / "dev" / "evals"
        self.roundFolder = self.evalsFolder / "round-1"
        self.siblingFolder = self.home / "dev" / "evals-old" / "round-1"
        self.otherFolder = self.home / "work" / "repo"
        for folder in (self.roundFolder, self.siblingFolder, self.otherFolder, self.home / ".claude"):
            folder.mkdir(parents=True)

    def environment(self, setting, projectFolder):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_PROJECT_DIR")}
        environment["HOME"] = str(self.homeInEnvironment)
        if setting is not None:
            environment["CLAUDE_TOOLKIT_TELEMETRY"] = setting
        if projectFolder is not None:
            environment["CLAUDE_PROJECT_DIR"] = str(projectFolder)
        return environment

    def switch_file(self, present):
        switchFile = self.home / ".claude" / "toolkit-telemetry"
        if present:
            switchFile.touch()
        else:
            switchFile.unlink(missing_ok=True)

    def is_on(self, setting=None, projectFolder=None, cwd=None, filePresent=False, deleteCwd=False):
        self.switch_file(filePresent)
        command = self.switch_command()
        if deleteCwd:
            # Start the switch from a current folder that was deleted after the shell entered it.
            command = ["bash", "-c", 'mkdir gone && cd gone && rmdir ../gone && exec "$@"', "bash"] + command
        finished = subprocess.run(command, env=self.environment(setting, projectFolder),
                                  cwd=str(cwd or self.otherFolder), capture_output=True, text=True)
        self.assertNotIn("Traceback", finished.stderr)
        if not deleteCwd:
            self.assertEqual(finished.stderr, "")
        self.assertIn(finished.returncode, (0, 1))
        return finished.returncode == 0

    def test_off_with_no_variable_and_no_file(self):
        self.assertFalse(self.is_on())

    def test_on_with_variable_one(self):
        self.assertTrue(self.is_on(setting="1"))

    def test_on_with_file(self):
        self.assertTrue(self.is_on(filePresent=True))

    def test_variable_zero_is_off_even_with_file(self):
        self.assertFalse(self.is_on(setting="0", filePresent=True))

    def test_variable_zero_is_off_with_project_folder_outside_evals(self):
        self.assertFalse(self.is_on(setting="0", projectFolder=self.otherFolder, filePresent=True))

    def test_file_inside_evals_project_folder_is_off(self):
        self.assertFalse(self.is_on(projectFolder=self.roundFolder, filePresent=True))

    def test_evals_folder_itself_is_inside(self):
        self.assertFalse(self.is_on(projectFolder=self.evalsFolder, filePresent=True))

    def test_variable_one_inside_evals_is_on(self):
        self.assertTrue(self.is_on(setting="1", projectFolder=self.roundFolder))

    def test_variable_zero_inside_evals_is_off(self):
        self.assertFalse(self.is_on(setting="0", projectFolder=self.roundFolder, filePresent=True))

    def test_evals_old_is_not_inside_evals(self):
        self.assertTrue(self.is_on(projectFolder=self.siblingFolder, filePresent=True))

    def test_symlink_into_evals_is_inside(self):
        link = self.root / "link-to-round"
        link.symlink_to(self.roundFolder)
        self.assertFalse(self.is_on(projectFolder=link, filePresent=True))

    def test_symlink_out_of_evals_is_not_inside(self):
        link = self.evalsFolder / "link-to-repo"
        link.symlink_to(self.otherFolder)
        self.assertTrue(self.is_on(projectFolder=link, filePresent=True))

    def test_current_folder_inside_evals_is_off_when_project_variable_unset(self):
        self.assertFalse(self.is_on(cwd=self.roundFolder, filePresent=True))

    def test_project_variable_wins_over_current_folder(self):
        self.assertTrue(self.is_on(projectFolder=self.otherFolder, cwd=self.roundFolder, filePresent=True))

    def test_project_folder_outside_evals_with_file_is_on(self):
        self.assertTrue(self.is_on(projectFolder=self.otherFolder, filePresent=True))

    def test_project_folder_outside_evals_without_file_is_off(self):
        self.assertFalse(self.is_on(projectFolder=self.otherFolder))

    def test_empty_project_variable_falls_back_to_current_folder_inside_evals(self):
        self.assertFalse(self.is_on(projectFolder="", cwd=self.roundFolder, filePresent=True))

    def test_empty_project_variable_falls_back_to_current_folder_outside_evals(self):
        self.assertTrue(self.is_on(projectFolder="", cwd=self.otherFolder, filePresent=True))

    def test_missing_project_folder_inside_evals_is_off(self):
        self.assertFalse(self.is_on(projectFolder=self.evalsFolder / "not-made-yet", filePresent=True))

    def test_missing_project_folder_outside_evals_is_on(self):
        self.assertTrue(self.is_on(projectFolder=self.otherFolder / "not-made-yet", filePresent=True))

    def test_missing_relative_project_folder_is_outside_evals(self):
        self.assertTrue(self.is_on(projectFolder="not-made-yet", cwd=self.roundFolder, filePresent=True))

    def test_dot_dot_through_missing_folder_into_evals_is_off(self):
        projectFolder = f"{self.evalsFolder}/not-made-yet/../round-1"
        self.assertFalse(self.is_on(projectFolder=projectFolder, filePresent=True))

    def test_missing_project_folder_under_symlinked_evals_folder(self):
        # The evals folder resolves to its real path and the missing folder stays as given, so they do not match.
        self.evalsFolder.rename(self.home / "dev" / "real-evals")
        self.evalsFolder.symlink_to(self.home / "dev" / "real-evals")
        self.assertTrue(self.is_on(projectFolder=self.evalsFolder / "not-made-yet", filePresent=True))

    def test_missing_project_folder_under_symlinked_home(self):
        homeLink = self.root / "home-link"
        homeLink.symlink_to(self.home)
        self.homeInEnvironment = homeLink
        self.assertTrue(self.is_on(projectFolder=homeLink / "dev" / "evals" / "not-made-yet", filePresent=True))

    def test_existing_project_folder_under_symlinked_home_is_inside(self):
        homeLink = self.root / "home-link"
        homeLink.symlink_to(self.home)
        self.homeInEnvironment = homeLink
        self.assertFalse(self.is_on(projectFolder=homeLink / "dev" / "evals" / "round-1", filePresent=True))

    def test_symlinked_evals_folder_holds_inside_projects(self):
        realEvals = self.home / "dev" / "real-evals"
        self.evalsFolder.rename(realEvals)
        self.evalsFolder.symlink_to(realEvals)
        self.assertFalse(self.is_on(projectFolder=self.evalsFolder / "round-1", filePresent=True))
        self.assertFalse(self.is_on(projectFolder=realEvals / "round-1", filePresent=True))
        self.assertFalse(self.is_on(projectFolder=self.evalsFolder, filePresent=True))
        self.assertTrue(self.is_on(projectFolder=self.siblingFolder, filePresent=True))

    def test_trailing_slash_inside_evals_is_off(self):
        self.assertFalse(self.is_on(projectFolder=f"{self.roundFolder}/", filePresent=True))

    def test_trailing_slash_outside_evals_is_on(self):
        self.assertTrue(self.is_on(projectFolder=f"{self.siblingFolder}/", filePresent=True))

    def test_trailing_slash_on_missing_folder_inside_evals_is_off(self):
        self.assertFalse(self.is_on(projectFolder=f"{self.evalsFolder}/not-made-yet/", filePresent=True))

    def test_other_variable_value_is_not_a_switch(self):
        self.assertFalse(self.is_on(setting="true"))
        self.assertTrue(self.is_on(setting="true", filePresent=True))
        self.assertFalse(self.is_on(setting="true", projectFolder=self.roundFolder, filePresent=True))

    def test_empty_variable_is_not_a_switch(self):
        self.assertFalse(self.is_on(setting=""))
        self.assertTrue(self.is_on(setting="", filePresent=True))

    def test_deleted_current_folder_with_relative_project_variable_does_not_crash(self):
        self.assertTrue(self.is_on(projectFolder="repo", filePresent=True, deleteCwd=True))

    def test_deleted_current_folder_counts_as_outside_evals(self):
        self.assertTrue(self.is_on(cwd=self.roundFolder, filePresent=True, deleteCwd=True))


class ShellSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [str(SCRIPT_DIR / "telemetry_enabled.sh")]


class PythonSwitchTest(SwitchCases, unittest.TestCase):
    def switch_command(self):
        return [sys.executable, "-I", "-c", PYTHON_RUNNER, str(SCRIPT_DIR)]


if __name__ == "__main__":
    unittest.main()
