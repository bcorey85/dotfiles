"""Checks for the stop lines that name the uncommitted change."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
MODULE = pathlib.Path(os.environ.get("UNCOMMITTED_HUNKS_MODULE") or toolkit_paths.REVIEW_DIR / "uncommitted_hunks.py")
module_spec = importlib.util.spec_from_file_location("uncommitted_hunks", MODULE)
uncommitted_hunks = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(uncommitted_hunks)

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}


class StopLinesTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
        (self.repo / "gone.txt").write_text("x\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env=GIT_ENV, check=True, capture_output=True)

    def test_stop_lines_is_prefixed_for_a_repo_and_names_the_reason_when_the_packet_has_no_repo(self):
        (self.repo / "new.txt").write_text("n\n")
        state = {"relaunch_args": ["--repo", str(self.repo)]}
        self.assertEqual(uncommitted_hunks.stop_lines(state), ["Uncommitted: new.txt (untracked)"])
        with tempfile.TemporaryDirectory() as folder:
            gone_repo = str(pathlib.Path(folder) / "removed-worktree")
        lines = uncommitted_hunks.stop_lines({"relaunch_args": ["--repo", gone_repo]})
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("Uncommitted: not read: "), lines)
        self.assertIn("no longer a git work tree", lines[0])


if __name__ == "__main__":
    unittest.main()
