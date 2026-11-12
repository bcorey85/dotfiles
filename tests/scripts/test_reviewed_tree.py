"""Checks for the reviewed-tree record: a reviewed tree keeps its credit after part of it is committed."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("REVIEWED_TREE_MODULE") or toolkit_paths.LIB_DIR / "reviewed_tree.py")
sys.path.insert(0, str(MODULE.parent))
module_spec = importlib.util.spec_from_file_location("reviewed_tree", MODULE)
reviewed_tree = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(reviewed_tree)

SESSION = "split-commit-session"


def git(top, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=top, check=True,
                   capture_output=True)


def write(top, name, content):
    (pathlib.Path(top) / name).write_text(content)


class SplitCommitCredit(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.home = pathlib.Path(self.directory) / "home"
        self.home.mkdir()
        self.repo = pathlib.Path(self.directory) / "repo"
        self.repo.mkdir()
        patched = mock.patch.dict(os.environ, {"HOME": str(self.home), "GIT_CONFIG_GLOBAL": os.devnull,
                                               "GIT_CONFIG_SYSTEM": os.devnull})
        patched.start()
        self.addCleanup(patched.stop)
        git(self.repo, "init", "-q")
        write(self.repo, "a.txt", "a\n")
        write(self.repo, "b.txt", "b\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")

    def record_two_file_change(self):
        write(self.repo, "a.txt", "a edited\n")
        write(self.repo, "b.txt", "b edited\n")
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo))

    def test_unchanged_tree_is_reviewed(self):
        self.record_two_file_change()
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_rest_of_tree_stays_reviewed_after_one_file_is_committed(self):
        self.record_two_file_change()
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_second_commit_of_the_split_keeps_credit(self):
        self.record_two_file_change()
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        git(self.repo, "commit", "-q", "-am", "second half")
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_re_record_replaces_the_stored_base_and_tree(self):
        self.record_two_file_change()
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo))
        git(self.repo, "commit", "-q", "-am", "second half")
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))
        write(self.repo, "a.txt", "unrelated edit\n")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_malformed_base_entry_is_not_reviewed(self):
        self.record_two_file_change()
        top = str(self.repo.resolve())
        reviewed_tree.base_file(SESSION).write_text(json.dumps({top: "junk"}))
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_non_string_base_value_is_not_reviewed(self):
        self.record_two_file_change()
        top = str(self.repo.resolve())
        tree_hash = reviewed_tree.reviewed_fingerprint(self.repo)[1]
        reviewed_tree.base_file(SESSION).write_text(json.dumps({top: {"base": 7, "tree": tree_hash}}))
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_stored_tree_taken_before_a_commit_stores_no_base(self):
        write(self.repo, "a.txt", "a edited\n")
        write(self.repo, "b.txt", "b edited\n")
        stored = reviewed_tree.reviewed_fingerprint(self.repo)
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo, tree=stored))
        self.assertFalse(reviewed_tree.base_file(SESSION).exists())
        git(self.repo, "commit", "-q", "-am", "second half")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_a_record_that_stores_no_base_drops_the_earlier_base(self):
        self.record_two_file_change()
        top = str(self.repo.resolve())
        self.assertIn(top, json.loads(reviewed_tree.base_file(SESSION).read_text()))
        second_tree = reviewed_tree.reviewed_fingerprint(self.repo)
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo, tree=second_tree))
        self.assertNotIn(top, json.loads(reviewed_tree.base_file(SESSION).read_text()))
        git(self.repo, "commit", "-q", "-am", "second half")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_stored_tree_taken_at_current_head_stores_base_and_credits_split(self):
        write(self.repo, "a.txt", "a edited\n")
        write(self.repo, "b.txt", "b edited\n")
        stored = reviewed_tree.reviewed_fingerprint(self.repo)
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo, tree=stored))
        self.assertTrue(reviewed_tree.base_file(SESSION).exists())
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        git(self.repo, "commit", "-q", "-am", "second half")
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_new_file_split_across_commits_stays_reviewed(self):
        write(self.repo, "new.txt", "new\n")
        write(self.repo, "b.txt", "b edited\n")
        self.assertTrue(reviewed_tree.record_reviewed(SESSION, self.repo))
        git(self.repo, "add", "new.txt")
        git(self.repo, "commit", "-q", "-m", "first half", "new.txt")
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_edit_after_first_commit_is_not_reviewed(self):
        self.record_two_file_change()
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        write(self.repo, "b.txt", "b edited again\n")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_edit_before_first_commit_is_not_reviewed(self):
        self.record_two_file_change()
        write(self.repo, "a.txt", "a edited again\n")
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_head_that_is_not_a_descendant_of_the_base_is_not_reviewed(self):
        self.record_two_file_change()
        git(self.repo, "checkout", "-q", "--orphan", "other")
        git(self.repo, "rm", "-rfq", "--cached", ".")
        write(self.repo, "a.txt", "a edited\n")
        write(self.repo, "b.txt", "b edited\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "unrelated root")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_missing_base_file_falls_back_to_the_head_check(self):
        self.record_two_file_change()
        reviewed_tree.base_file(SESSION).unlink()
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))
        git(self.repo, "commit", "-q", "-m", "first half", "a.txt")
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_unborn_repo_records_no_base_and_is_not_reviewed(self):
        unborn = pathlib.Path(self.directory) / "unborn"
        unborn.mkdir()
        git(unborn, "init", "-q")
        write(unborn, "x.txt", "x\n")
        self.assertFalse(reviewed_tree.record_reviewed(SESSION, unborn))
        self.assertFalse(reviewed_tree.base_file(SESSION).exists())
        self.assertFalse(reviewed_tree.is_reviewed(SESSION, unborn))


if __name__ == "__main__":
    unittest.main()
