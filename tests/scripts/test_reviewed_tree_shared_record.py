"""Checks for reviewed_tree.shared_record_covers: the shared record any session wrote, read with no session.

run: python3 tests/scripts/test_reviewed_tree_shared_record.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import reviewed_tree

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


class SharedRecordCovers(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = pathlib.Path(directory.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        home = root / "home"
        home.mkdir()
        patcher = mock.patch.dict(os.environ, {**GIT_ENV, "HOME": str(home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.git("init", "-q", "-b", "master")
        (self.repo / "a.txt").write_text("one\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def test_the_tree_another_session_recorded_is_covered(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))

        self.assertTrue(reviewed_tree.shared_record_covers(self.repo))

    def test_a_clean_tree_is_not_covered_even_with_the_empty_change_recorded(self):
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        recorded = reviewed_tree.read_shared_reviewed()[str(self.repo.resolve())]
        self.assertIn(reviewed_tree.NO_CHANGE_FINGERPRINT, recorded)

        self.assertFalse(reviewed_tree.shared_record_covers(self.repo))

    def test_a_directory_outside_any_work_tree_is_not_covered(self):
        with tempfile.TemporaryDirectory() as outside:
            self.assertFalse(reviewed_tree.shared_record_covers(outside))

    def test_an_edit_to_a_notes_path_does_not_change_what_is_covered(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "note.md").write_text("later note\n")

        self.assertTrue(reviewed_tree.shared_record_covers(self.repo))

    def test_an_edit_after_the_recorded_review_is_not_covered(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        (self.repo / "a.txt").write_text("three\n")

        self.assertFalse(reviewed_tree.shared_record_covers(self.repo))

    def test_the_credit_survives_committing_the_reviewed_change(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        self.git("commit", "-q", "-am", "reviewed change")

        self.assertTrue(reviewed_tree.shared_record_covers(self.repo))

    def test_the_credit_survives_committing_the_reviewed_change_together_with_a_notes_file(self):
        (self.repo / "a.txt").write_text("two\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "note.md").write_text("note\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "reviewed change and note")

        self.assertTrue(reviewed_tree.shared_record_covers(self.repo))

    def test_a_commit_of_an_unreviewed_change_is_not_covered(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        (self.repo / "a.txt").write_text("three\n")
        self.git("commit", "-q", "-am", "other change")

        self.assertFalse(reviewed_tree.shared_record_covers(self.repo))

    def test_a_clean_tree_whose_head_is_a_merge_is_not_covered(self):
        self.git("checkout", "-q", "-b", "side")
        (self.repo / "b.txt").write_text("side\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "side change")
        self.git("checkout", "-q", "master")
        (self.repo / "a.txt").write_text("two\n")
        self.git("commit", "-q", "-am", "master change")
        self.git("merge", "-q", "--no-ff", "--no-commit", "side")
        self.assertTrue(reviewed_tree.record_reviewed("other-session", self.repo))
        self.git("commit", "-q", "-m", "merge side")

        self.assertFalse(reviewed_tree.shared_record_covers(self.repo))

    def test_a_tree_nothing_recorded_is_not_covered(self):
        (self.repo / "a.txt").write_text("two\n")
        self.assertFalse(reviewed_tree.shared_record_covers(self.repo))


if __name__ == "__main__":
    unittest.main()
