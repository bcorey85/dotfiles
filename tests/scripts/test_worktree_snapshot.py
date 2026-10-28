"""Tests for worktree_snapshot.py: naming what a command changed in a git work tree, and leaving it in place."""
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import worktree_snapshot


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class WorktreeSnapshotTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        (self.repo / "generated.ts").write_text("generated v1\n")
        (self.repo / "app.py").write_text("app v1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "files")

    def test_a_file_that_cannot_be_read_hashes_to_a_stable_sentinel_instead_of_crashing_take(self):
        (self.repo / "secret.txt").write_text("hidden\n")
        real_open = pathlib.Path.open

        def refuse(path, *args, **kwargs):
            if path.name == "secret.txt":
                raise PermissionError("denied")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(pathlib.Path, "open", refuse):
            before = worktree_snapshot.take(self.repo)

        self.assertEqual(worktree_snapshot.UNREADABLE, before["hashes"]["secret.txt"])

    def test_a_tracked_file_the_command_rewrote_is_named_and_left_as_written(self):
        before = worktree_snapshot.take(self.repo)
        (self.repo / "generated.ts").write_text("generated v2\n")

        changed, rewrote_edited, created = worktree_snapshot.changes_since(before)

        self.assertEqual((["generated.ts"], [], []), (changed, rewrote_edited, created))
        self.assertEqual("generated v2\n", (self.repo / "generated.ts").read_text())

    def test_a_file_that_was_dirty_before_is_named_as_rewrote_edited_whether_rewritten_or_reverted(self):
        (self.repo / "app.py").write_text("app edited by the coder\n")
        (self.repo / "generated.ts").write_text("generated edited by the coder\n")
        before = worktree_snapshot.take(self.repo)
        (self.repo / "app.py").write_text("app rewritten by the check\n")
        git(self.repo, "checkout", "--", "generated.ts")

        changed, rewrote_edited, created = worktree_snapshot.changes_since(before)

        self.assertEqual(([], ["app.py", "generated.ts"], []), (changed, rewrote_edited, created))
        self.assertEqual("app rewritten by the check\n", (self.repo / "app.py").read_text())
        self.assertEqual("generated v1\n", (self.repo / "generated.ts").read_text())

    def test_a_file_that_was_dirty_before_and_holds_the_same_bytes_is_not_named(self):
        (self.repo / "app.py").write_text("app edited by the coder\n")
        before = worktree_snapshot.take(self.repo)

        self.assertEqual(([], [], []), worktree_snapshot.changes_since(before))

    def test_an_untracked_file_the_command_created_is_named_and_left_in_place(self):
        (self.repo / "old-note.txt").write_text("there before\n")
        before = worktree_snapshot.take(self.repo)
        (self.repo / "dist").mkdir()
        (self.repo / "dist" / "bundle.js").write_text("built\n")

        changed, rewrote_edited, created = worktree_snapshot.changes_since(before)

        self.assertEqual(([], [], ["dist/bundle.js"]), (changed, rewrote_edited, created))
        self.assertTrue((self.repo / "dist" / "bundle.js").is_file())

    def test_an_untracked_file_that_was_there_before_and_was_rewritten_is_named_as_rewrote_edited(self):
        (self.repo / "new.py").write_text("coder work\n")
        before = worktree_snapshot.take(self.repo)
        (self.repo / "new.py").write_text("rewritten by the check\n")

        self.assertEqual(([], ["new.py"], []), worktree_snapshot.changes_since(before))

    def test_a_folder_that_is_no_git_work_tree_is_left_alone(self):
        with tempfile.TemporaryDirectory() as bare_folder:
            before = worktree_snapshot.take(bare_folder)

            self.assertIsNone(before)
            self.assertEqual(([], [], []), worktree_snapshot.changes_since(before))


if __name__ == "__main__":
    unittest.main()
