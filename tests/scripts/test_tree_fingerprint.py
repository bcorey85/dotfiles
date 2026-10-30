"""Checks for reviewed_tree.tree_fingerprint, the one working-tree hash behind verify's stored fingerprints and the
review commit gate's reviewed-tree record."""
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

sys.path.insert(0, str(toolkit_paths.SCRIPTS_DIR / "lib"))
import reviewed_tree

# Recorded from verify_common.branch_fingerprint before it was removed: verify contexts and ledger review rows
# written earlier hold these exact bytes, so the shared formula must keep returning them.
GOLDEN_WHOLE_TREE = "sha256:96469e8d0fa2984474bf663951c11ca17740dab5cc2a3117c293b71fac7b8ee1"
GOLDEN_WITHOUT_TASK_DIR = "sha256:9f1d9672d31f1dae55fcb65535c10fd47decdd3777c067038670c23f6321825e"
EXCLUDED_DIR = "task"


def git(top, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=top, check=True,
                   capture_output=True)


def write(top, name, content):
    path = pathlib.Path(top) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_fixture(top):
    """A repo with a committed file, an edit to it, an untracked file and an untracked file in an excluded dir."""
    git(top, "init", "-q")
    write(top, "kept.txt", b"first line\nsecond line\n")
    write(top, f"{EXCLUDED_DIR}/notes.md", b"committed notes\n")
    git(top, "add", ".")
    git(top, "commit", "-q", "-m", "base")
    write(top, "kept.txt", b"first line\nsecond line edited\n")
    write(top, f"{EXCLUDED_DIR}/notes.md", b"committed notes\nedited notes\n")
    write(top, "new.txt", b"untracked content\n")
    write(top, f"{EXCLUDED_DIR}/extra.md", b"untracked in excluded dir\n")


class TreeFingerprint(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.top = pathlib.Path(self.directory)
        build_fixture(self.top)

    def test_whole_tree_keeps_the_bytes_verify_stored(self):
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top), GOLDEN_WHOLE_TREE)

    def test_excluded_dir_keeps_the_bytes_verify_stored(self):
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_edit_inside_excluded_dir_leaves_the_value(self):
        write(self.top, f"{EXCLUDED_DIR}/extra.md", b"changed again\n")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_edit_outside_excluded_dir_changes_the_value(self):
        write(self.top, "new.txt", b"other\n")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_non_utf8_untracked_name_is_fingerprinted(self):
        non_utf8_name = os.fsdecode(b"n\xe9")
        write(self.top, non_utf8_name, b"x\n")
        first = reviewed_tree.tree_fingerprint(self.top)
        self.assertNotEqual(first, GOLDEN_WHOLE_TREE)

        write(self.top, non_utf8_name, b"y\n")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), first)

    def test_edit_to_non_utf8_tracked_bytes_changes_the_value(self):
        write(self.top, "bin.dat", b"\xff\x01")
        git(self.top, "add", "bin.dat")
        git(self.top, "commit", "-q", "-m", "bin")
        first = reviewed_tree.tree_fingerprint(self.top)
        write(self.top, "bin.dat", b"\xfe\x01")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), first)

    def test_untracked_name_that_only_starts_like_excluded_dir_is_counted(self):
        write(self.top, f"{EXCLUDED_DIR}-other.md", b"sibling\n")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_newline_in_untracked_name_is_refused(self):
        write(self.top, "bad\nname.txt", b"x\n")
        with self.assertRaisesRegex(reviewed_tree.TreeFingerprintError, "holds a newline"):
            reviewed_tree.tree_fingerprint(self.top)

    def test_git_failure_raises_the_error_type(self):
        with self.assertRaisesRegex(reviewed_tree.TreeFingerprintError, "failed"):
            reviewed_tree.tree_fingerprint(self.top, "no-such-ref")

    def test_caller_error_type_is_raised_instead(self):
        class OwnError(Exception):
            pass

        with self.assertRaises(OwnError):
            reviewed_tree.tree_fingerprint(self.top, "no-such-ref", error_type=OwnError)

    def test_fingerprint_is_top_and_the_same_value(self):
        top = pathlib.Path(self.directory).resolve()
        found = reviewed_tree.fingerprint(self.top)
        self.assertEqual(found, (str(top), GOLDEN_WHOLE_TREE))

    def test_fingerprint_is_none_when_git_fails(self):
        with mock.patch.object(reviewed_tree, "tree_fingerprint",
                               side_effect=reviewed_tree.TreeFingerprintError("boom")):
            self.assertIsNone(reviewed_tree.fingerprint(self.top))


class StaleReviewedRecord(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.top = pathlib.Path(self.directory) / "repo"
        self.top.mkdir()
        build_fixture(self.top)
        home = pathlib.Path(self.directory) / "home"
        home.mkdir()
        patcher = mock.patch.object(pathlib.Path, "home", return_value=home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bare_hex_record_of_the_current_tree_is_not_reviewed_until_rerecorded(self):
        top, value = reviewed_tree.fingerprint(self.top)
        bare_hex = value.removeprefix("sha256:")
        reviewed_tree.review_gate_dir().mkdir(parents=True)
        reviewed_tree.reviewed_file("s1").write_text(json.dumps({top: bare_hex}) + "\n")

        self.assertFalse(reviewed_tree.is_reviewed("s1", self.top))
        self.assertTrue(reviewed_tree.record_reviewed("s1", self.top))
        self.assertTrue(reviewed_tree.is_reviewed("s1", self.top))


if __name__ == "__main__":
    unittest.main()
