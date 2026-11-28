"""Sources lane-env.zsh in a bare zsh and reads back CLAUDE_CODE_DISABLE_CRON.

A fake HOME holds the lane files; the shell's cwd is a fake worktree. The parent environment's
CLAUDE_CODE_DISABLE_CRON is stripped so only the sourced file can set it.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import lane_entries

LANE_ENV = pathlib.Path(os.environ.get("LANE_ENV_ZSH") or
                        toolkit_paths.REPO_ROOT / "scripts" / ".local" / "lib" / "lane-env.zsh")
NAME = "repo-lane"


class LaneEnvTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name).resolve()
        self.home = root / "home"
        self.worktree = root / "work" / NAME
        self.worktree.mkdir(parents=True)
        self.state = self.home / ".local" / "state"

    def write_lane_file(self, worktree, xdg_state=True):
        """Writes the lane file through the owner, so a change to its folder or format fails these tests."""
        env = {"HOME": str(self.home)}
        if xdg_state:
            env["XDG_STATE_HOME"] = str(self.state)
        with unittest.mock.patch.dict(os.environ, env):
            if not xdg_state:
                os.environ.pop("XDG_STATE_HOME", None)
            lane_entries.add_entry(NAME, str(worktree), str(self.home), "x", "brief", "orchestrator")

    def read_cron(self, herdr_env: str | None = "1", xdg_state=True, cwd=None, pwd=None, state_home=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CODE_DISABLE_CRON", "HERDR_ENV", "XDG_STATE_HOME")}
        env["HOME"] = str(self.home)
        if pwd is not None:
            # subprocess cwd= alone gives zsh the physical path; this keeps $PWD logical through a symlink
            env["PWD"] = pwd
        if xdg_state:
            env["XDG_STATE_HOME"] = str(self.state)
        if state_home is not None:
            env["XDG_STATE_HOME"] = state_home
        if herdr_env is not None:
            env["HERDR_ENV"] = herdr_env
        script = f"source {LANE_ENV}; print -r -- ${{CLAUDE_CODE_DISABLE_CRON-unset}}"
        run = subprocess.run(["zsh", "-f", "-c", script], cwd=cwd or self.worktree, env=env,
                             capture_output=True, text=True, check=True)
        return run.stdout.strip()

    def test_lane_worktree_in_herdr_disables_cron(self):
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(), "1")

    def test_lane_worktree_under_non_ascii_parent_disables_cron(self):
        worktree = self.worktree.parent / "wérk" / NAME
        worktree.mkdir(parents=True)
        self.write_lane_file(worktree)
        self.assertEqual(self.read_cron(cwd=worktree), "1")

    def test_worktree_parent_holding_a_double_quote_disables_cron(self):
        worktree = self.worktree.parent / 'quo"te' / NAME
        worktree.mkdir(parents=True)
        self.write_lane_file(worktree)
        self.assertEqual(self.read_cron(cwd=worktree), "1")

    def test_worktree_parent_holding_a_backslash_disables_cron(self):
        worktree = self.worktree.parent / "back\\slash" / NAME
        worktree.mkdir(parents=True)
        self.write_lane_file(worktree)
        self.assertEqual(self.read_cron(cwd=worktree), "1")

    def test_worktree_reached_through_a_symlinked_parent_disables_cron(self):
        link = self.worktree.parent.parent / "link"
        link.symlink_to(self.worktree.parent)
        self.write_lane_file(self.worktree)
        logical = link / NAME
        self.assertEqual(self.read_cron(cwd=logical, pwd=str(logical)), "1")

    def test_worktree_itself_reached_through_a_differently_named_symlink_disables_cron(self):
        link = self.worktree.parent / "alias"
        link.symlink_to(self.worktree)
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(cwd=link, pwd=str(link)), "1")

    def test_non_lane_directory_leaves_cron_alone(self):
        self.write_lane_file(self.worktree)
        other = self.worktree.parent / "other"
        other.mkdir()
        self.assertEqual(self.read_cron(cwd=other), "unset")

    def test_outside_herdr_leaves_cron_alone(self):
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(herdr_env=None), "unset")

    def test_lane_file_naming_another_worktree_leaves_cron_alone(self):
        self.write_lane_file(self.worktree.parent / "elsewhere" / NAME)
        self.assertEqual(self.read_cron(), "unset")

    def test_lane_file_naming_a_longer_path_leaves_cron_alone(self):
        self.write_lane_file(pathlib.Path(str(self.worktree) + "2"))
        self.assertEqual(self.read_cron(), "unset")

    def test_herdr_env_other_than_1_leaves_cron_alone(self):
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(herdr_env="0"), "unset")

    def test_state_home_falls_back_to_home_local_state(self):
        self.write_lane_file(self.worktree, xdg_state=False)
        self.assertEqual(self.read_cron(xdg_state=False), "1")

    def test_a_relative_state_home_is_ignored_like_the_writer_does(self):
        self.write_lane_file(self.worktree, xdg_state=False)
        self.assertEqual(self.read_cron(xdg_state=False, state_home="relative/state"), "1")


if __name__ == "__main__":
    unittest.main()
