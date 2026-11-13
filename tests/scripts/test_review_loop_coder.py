"""Tests for review_loop_coder.coder_call: which untracked files a coder may delete."""
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_coder


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class UntrackedDeletionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.out = pathlib.Path(tmp.name) / "out"
        self.repo.mkdir()
        self.out.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "app.py").write_text("x = 1\n")
        git(self.repo, "add", "app.py")
        git(self.repo, "commit", "-qm", "init")
        review_loop_coder.UNTRACKED_FAULTS.clear()
        review_loop_coder.LOOP_WRITTEN.clear()
        self.addCleanup(review_loop_coder.UNTRACKED_FAULTS.clear)
        self.addCleanup(review_loop_coder.LOOP_WRITTEN.clear)

    def call(self, role, action):
        """Runs coder_call with a stand-in model call that runs `action(repo)`."""
        def fake_claude(*_args, **_kwargs):
            action(self.repo)
            return "done"

        with mock.patch.object(review_loop_coder, "claude_call", fake_claude):
            return review_loop_coder.coder_call(role, "prompt", self.repo, self.out, set())

    def test_a_file_an_earlier_call_made_stays_deleted_with_no_fault_note(self):
        self.call("coder1", lambda repo: (repo / "dup.py").write_text("dup\n"))
        self.call("coder2", lambda repo: (repo / "dup.py").unlink())

        self.assertFalse((self.repo / "dup.py").exists())
        self.assertEqual(review_loop_coder.UNTRACKED_FAULTS, [])
        self.assertNotIn("dup.py", review_loop_coder.LOOP_WRITTEN)

    def test_a_file_a_failed_call_made_stays_deleted_with_no_fault_note(self):
        def write_then_die(repo):
            (repo / "dup.py").write_text("dup\n")
            raise RuntimeError("coder died")

        with self.assertRaises(RuntimeError):
            self.call("coder1", write_then_die)
        self.call("coder2", lambda repo: (repo / "dup.py").unlink())

        self.assertFalse((self.repo / "dup.py").exists())
        self.assertEqual(review_loop_coder.UNTRACKED_FAULTS, [])

    def test_a_file_that_existed_before_the_loop_is_restored_with_the_fault_note(self):
        (self.repo / "mine.py").write_text("mine\n")
        self.call("coder1", lambda repo: (repo / "mine.py").unlink())

        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")
        self.assertEqual(len(review_loop_coder.UNTRACKED_FAULTS), 1)
        self.assertIn("mine.py", review_loop_coder.UNTRACKED_FAULTS[0])

    def test_a_file_that_appears_between_calls_without_a_coder_is_restored(self):
        self.call("coder1", lambda repo: (repo / "app.py").write_text("x = 2\n"))
        (self.repo / "theirs.py").write_text("theirs\n")
        self.call("coder2", lambda repo: (repo / "theirs.py").unlink())

        self.assertEqual((self.repo / "theirs.py").read_text(), "theirs\n")
        self.assertEqual(len(review_loop_coder.UNTRACKED_FAULTS), 1)
        self.assertIn("theirs.py", review_loop_coder.UNTRACKED_FAULTS[0])


if __name__ == "__main__":
    unittest.main()
