"""Sources lane-env.zsh in a bare zsh and reads back CLAUDE_CODE_DISABLE_CRON.

A fake HOME holds the lane files; the shell's cwd is a fake worktree. The parent environment's
CLAUDE_CODE_DISABLE_CRON is stripped so only the sourced file can set it.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

LANE_ENV = pathlib.Path(os.environ.get("LANE_ENV_ZSH") or
                        pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "lib" / "lane-env.zsh")
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

    def write_lane_file(self, worktree, state_dir=None):
        lanes_dir = (state_dir or self.state) / "herdr-lanes"
        lanes_dir.mkdir(parents=True, exist_ok=True)
        lane = {"name": NAME, "worktree": str(worktree), "branch": "x"}
        (lanes_dir / f"{NAME}.json").write_text(json.dumps(lane, indent=2))

    def read_cron(self, herdr_env: str | None = "1", xdg_state=True, cwd=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CODE_DISABLE_CRON", "HERDR_ENV", "XDG_STATE_HOME")}
        env["HOME"] = str(self.home)
        if xdg_state:
            env["XDG_STATE_HOME"] = str(self.state)
        if herdr_env is not None:
            env["HERDR_ENV"] = herdr_env
        script = f"source {LANE_ENV}; print -r -- ${{CLAUDE_CODE_DISABLE_CRON-unset}}"
        run = subprocess.run(["zsh", "-f", "-c", script], cwd=cwd or self.worktree, env=env,
                             capture_output=True, text=True, check=True)
        return run.stdout.strip()

    def test_lane_worktree_in_herdr_disables_cron(self):
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(), "1")

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

    def test_state_home_falls_back_to_home_local_state(self):
        self.write_lane_file(self.worktree)
        self.assertEqual(self.read_cron(xdg_state=False), "1")


if __name__ == "__main__":
    unittest.main()
