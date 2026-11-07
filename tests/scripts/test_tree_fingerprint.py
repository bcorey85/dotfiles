"""Checks for reviewed_tree.tree_fingerprint, the one working-tree hash behind verify's stored fingerprints and the
review commit gate's reviewed-tree record."""
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


def head(top):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=top, check=True, capture_output=True,
                          text=True).stdout.strip()


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
        isolated_git_config = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull,
                                                           "GIT_CONFIG_SYSTEM": os.devnull})
        isolated_git_config.start()
        self.addCleanup(isolated_git_config.stop)
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

    def test_a_staged_new_file_has_the_value_of_the_same_file_untracked(self):
        untracked = reviewed_tree.tree_fingerprint(self.top)
        git(self.top, "add", "new.txt")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top), untracked)

    def test_a_staged_move_has_the_value_of_the_plain_move(self):
        git(self.top, "add", "kept.txt")
        git(self.top, "commit", "-q", "-m", "edit")
        os.rename(self.top / "kept.txt", self.top / "moved.txt")
        plain = reviewed_tree.tree_fingerprint(self.top)
        git(self.top, "add", "-A", "kept.txt", "moved.txt")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top), plain)

    def test_a_staged_new_file_edited_further_changes_the_value(self):
        git(self.top, "add", "new.txt")
        staged = reviewed_tree.tree_fingerprint(self.top)
        write(self.top, "new.txt", b"edited after staging\n")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), staged)

    def test_a_file_committed_on_top_of_base_has_the_value_of_the_same_file_untracked(self):
        base = head(self.top)
        untracked = reviewed_tree.tree_fingerprint(self.top, base)
        git(self.top, "add", "new.txt")
        git(self.top, "commit", "-q", "-m", "add new file")
        self.assertNotEqual(head(self.top), base)
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, base), untracked)

    def test_a_submodule_added_since_base_is_fingerprinted(self):
        base = head(self.top)
        with tempfile.TemporaryDirectory() as sub_directory:
            sub = pathlib.Path(sub_directory)
            git(sub, "init", "-q")
            write(sub, "f.txt", b"x\n")
            git(sub, "add", ".")
            git(sub, "commit", "-q", "-m", "sub")
            git(self.top, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendored")
        git(self.top, "commit", "-q", "-m", "add submodule")
        first = reviewed_tree.tree_fingerprint(self.top, base)
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, base), first)
        write(self.top / "vendored", "g.txt", b"y\n")
        git(self.top / "vendored", "add", ".")
        git(self.top / "vendored", "commit", "-q", "-m", "move the submodule")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top, base), first)

    def test_untracked_nested_repo_is_refused(self):
        nested = self.top / "nested"
        nested.mkdir()
        git(nested, "init", "-q")
        write(nested, "f.txt", b"x\n")
        with self.assertRaisesRegex(reviewed_tree.TreeFingerprintError, "nested repository"):
            reviewed_tree.tree_fingerprint(self.top)

    def test_untracked_symlinks_are_hashed_by_link_text(self):
        for name, target in (("dangling", "missing-target"), ("dir-link", EXCLUDED_DIR)):
            with self.subTest(name=name):
                os.symlink(target, self.top / name)
                first = reviewed_tree.tree_fingerprint(self.top)
                self.assertNotEqual(first, GOLDEN_WHOLE_TREE)
                os.unlink(self.top / name)
                os.symlink("other-target", self.top / name)
                self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), first)
                os.unlink(self.top / name)

    def test_a_staged_symlink_to_a_directory_is_fingerprinted_by_link_text(self):
        os.symlink(EXCLUDED_DIR, self.top / "dir-link")
        git(self.top, "add", "dir-link")
        first = reviewed_tree.tree_fingerprint(self.top)
        self.assertNotEqual(first, GOLDEN_WHOLE_TREE)
        os.unlink(self.top / "dir-link")
        os.symlink("other-target", self.top / "dir-link")
        git(self.top, "add", "dir-link")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), first)

    def test_a_staged_symlink_to_a_file_is_not_followed(self):
        write(self.top, "a.txt", b"same\n")
        write(self.top, "b.txt", b"same\n")
        os.symlink("a.txt", self.top / "link")
        git(self.top, "add", "link")
        first = reviewed_tree.tree_fingerprint(self.top)
        os.unlink(self.top / "link")
        os.symlink("b.txt", self.top / "link")
        git(self.top, "add", "link")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), first)

    def test_a_symlink_committed_on_top_of_base_is_hashed_by_link_text(self):
        base = head(self.top)
        write(self.top, "a.txt", b"same\n")
        git(self.top, "add", "a.txt")
        os.symlink("a.txt", self.top / "link")
        untracked = reviewed_tree.tree_fingerprint(self.top, base)
        git(self.top, "add", "a.txt", "link")
        git(self.top, "commit", "-q", "-m", "add symlink")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, base), untracked)
        os.remove(self.top / "link")
        os.symlink("other-target", self.top / "link")
        git(self.top, "add", "link")
        git(self.top, "commit", "-q", "-m", "retarget symlink")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top, base), untracked)

    def test_a_symlink_has_the_same_value_untracked_and_staged(self):
        write(self.top, "a.txt", b"same\n")
        git(self.top, "add", "a.txt")
        os.symlink("a.txt", self.top / "link")
        untracked = reviewed_tree.tree_fingerprint(self.top)
        git(self.top, "add", "link")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top), untracked)

    def test_a_staged_symlink_in_the_excluded_dir_leaves_the_value(self):
        os.symlink("a.txt", self.top / EXCLUDED_DIR / "link")
        git(self.top, "add", f"{EXCLUDED_DIR}/link")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_newline_in_untracked_or_staged_name_is_refused(self):
        write(self.top, "bad\nname.txt", b"x\n")
        with self.assertRaisesRegex(reviewed_tree.TreeFingerprintError, "holds a newline"):
            reviewed_tree.tree_fingerprint(self.top)
        git(self.top, "add", "bad\nname.txt")
        with self.assertRaisesRegex(reviewed_tree.TreeFingerprintError, "holds a newline"):
            reviewed_tree.tree_fingerprint(self.top)

    def test_a_staged_file_in_the_excluded_dir_leaves_the_value(self):
        git(self.top, "add", f"{EXCLUDED_DIR}/extra.md")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, "HEAD", EXCLUDED_DIR), GOLDEN_WITHOUT_TASK_DIR)

    def test_a_staged_notes_file_leaves_the_value_when_notes_entries_are_given(self):
        before = reviewed_tree.tree_fingerprint(self.top, notes_entries=[])
        write(self.top, "docs/plan.md", b"ticked\n")
        git(self.top, "add", "docs/plan.md")
        self.assertEqual(reviewed_tree.tree_fingerprint(self.top, notes_entries=[]), before)
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), before)

    def test_git_rm_cached_of_a_tracked_file_changes_the_value(self):
        git(self.top, "add", "kept.txt")
        git(self.top, "commit", "-q", "-m", "edit")
        before = reviewed_tree.tree_fingerprint(self.top)
        git(self.top, "rm", "-q", "--cached", "kept.txt")
        self.assertNotEqual(reviewed_tree.tree_fingerprint(self.top), before)

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

    def test_reviewed_fingerprint_of_a_tree_with_no_notes_path_is_the_whole_tree_value(self):
        top = pathlib.Path(self.directory).resolve()
        self.assertEqual(reviewed_tree.reviewed_fingerprint(self.top), (str(top), GOLDEN_WHOLE_TREE))

    def test_a_docs_markdown_edit_changes_the_whole_tree_value_and_not_the_reviewed_one(self):
        reviewed_before = reviewed_tree.reviewed_fingerprint(self.top)
        write(self.top, "docs/plan.md", b"ticked\n")
        self.assertNotEqual(reviewed_tree.fingerprint(self.top)[1], GOLDEN_WHOLE_TREE)
        self.assertEqual(reviewed_tree.reviewed_fingerprint(self.top), reviewed_before)

    def test_fingerprint_is_none_when_git_fails(self):
        with mock.patch.object(reviewed_tree, "tree_fingerprint",
                               side_effect=reviewed_tree.TreeFingerprintError("boom")):
            self.assertIsNone(reviewed_tree.fingerprint(self.top))

    def test_fingerprint_base_is_the_head_commit_in_a_repo_with_a_commit(self):
        commit = head(self.top)
        self.assertEqual(reviewed_tree.fingerprint_base(self.top), (commit, commit))

    def test_fingerprint_base_is_the_empty_tree_in_a_repo_with_no_commit(self):
        with tempfile.TemporaryDirectory() as bare:
            git(bare, "init", "-q")
            empty_tree = subprocess.run(["git", "hash-object", "-t", "tree", os.devnull], cwd=bare, check=True,
                                        capture_output=True, text=True).stdout.strip()
            self.assertEqual(reviewed_tree.fingerprint_base(bare), ("unborn", empty_tree))


if __name__ == "__main__":
    unittest.main()
