"""Tests for worktree_snapshot.py: naming what a command changed in a git work tree, and leaving it in place."""
import os
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

    def test_working_tree_changes_give_each_dirty_file_its_code_blob_hash_and_line_counts(self):
        (self.repo / "app.py").write_text("app v2\nmore\n")
        (self.repo / "new.py").write_text("one\ntwo\nthree")
        (self.repo / "generated.ts").unlink()
        git(self.repo, "mv", "app.py", "main.py")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual(["generated.ts", "main.py", "new.py"], sorted(changes))
        self.assertEqual({"code": "??", "hash": git(self.repo, "hash-object", "new.py"), "added": 3, "deleted": 0,
                          "new": True}, changes["new.py"])
        self.assertEqual({"code": " D", "hash": None, "added": 0, "deleted": 1, "new": False},
                         changes["generated.ts"])
        self.assertFalse(changes["main.py"]["new"])
        self.assertEqual(git(self.repo, "hash-object", "main.py"), changes["main.py"]["hash"])
        self.assertEqual("R", changes["main.py"]["code"][0])
        self.assertEqual(2, changes["main.py"]["added"])

    def test_a_pure_rename_adds_no_lines_whatever_the_diff_renames_setting(self):
        (self.repo / "big.py").write_text("".join(f"line {number}\n" for number in range(50)))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "big")
        git(self.repo, "config", "diff.renames", "false")
        git(self.repo, "mv", "big.py", "moved.py")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual((0, 0), (changes["moved.py"]["added"], changes["moved.py"]["deleted"]))

    def test_a_rename_is_one_moved_path_whatever_the_status_renames_setting(self):
        (self.repo / "big.py").write_text("".join(f"line {number}\n" for number in range(50)))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "big")
        git(self.repo, "config", "status.renames", "false")
        git(self.repo, "mv", "big.py", "moved.py")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertFalse(changes["moved.py"]["new"])
        self.assertNotIn("big.py", changes)

    def test_a_rename_in_the_worktree_column_is_one_moved_path_with_its_old_path_skipped(self):
        (self.repo / "big.py").write_text("".join(f"line {number}\n" for number in range(50)))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "big")
        (self.repo / "moved.py").write_text((self.repo / "big.py").read_text())
        git(self.repo, "add", "-N", "moved.py")
        (self.repo / "big.py").unlink()
        status = subprocess.run(["git", "status", "--porcelain", "--find-renames"], cwd=self.repo,
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(" R big.py -> moved.py\n", status)

        codes = worktree_snapshot.status_codes(self.repo)

        self.assertEqual(["moved.py"], list(codes))

    def test_a_tracked_file_with_a_quoted_name_keeps_its_line_counts(self):
        (self.repo / "q\"uote\tname.py").write_text("one\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "odd")
        (self.repo / "q\"uote\tname.py").write_text("one\ntwo\nthree\n")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual(2, changes["q\"uote\tname.py"]["added"])

    def test_working_tree_changes_of_a_clean_tree_are_empty(self):
        self.assertEqual({}, worktree_snapshot.working_tree_changes(self.repo))

    def test_working_tree_changes_mark_untracked_staged_and_intent_to_add_files_as_new(self):
        (self.repo / "untracked.py").write_text("one\n")
        (self.repo / "staged.py").write_text("one\n")
        (self.repo / "intent.py").write_text("one\n")
        git(self.repo, "add", "staged.py")
        git(self.repo, "add", "-N", "intent.py")
        (self.repo / "app.py").write_text("app v2\n")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual({"untracked.py": True, "staged.py": True, "intent.py": True, "app.py": False},
                         {path: change["new"] for path, change in changes.items()})

    def test_hashes_taken_in_several_chunks_equal_the_blob_hashes(self):
        (self.repo / "app.py").write_text("app v2\n")
        (self.repo / "one.py").write_text("one\n")
        (self.repo / "two.py").write_text("two\n")

        real_git_output = worktree_snapshot.git_output
        hash_object_calls = []

        def spy(root, *args):
            if args[0] == "hash-object":
                hash_object_calls.append(args)
            return real_git_output(root, *args)

        with (
            mock.patch.object(worktree_snapshot, "HASH_CHUNK_SIZE", 2),
            mock.patch.object(worktree_snapshot, "git_output", spy),
        ):
            changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual(2, len(hash_object_calls))
        self.assertEqual(["app.py", "one.py", "two.py"], sorted(changes))
        for path, change in changes.items():
            self.assertEqual(git(self.repo, "hash-object", path), change["hash"], path)

    def test_a_symlink_to_a_file_hashes_as_its_target_bytes_and_a_symlink_to_nothing_has_no_hash(self):
        (self.repo / "link.py").symlink_to("app.py")
        (self.repo / "dangling.py").symlink_to("missing.py")

        changes = worktree_snapshot.working_tree_changes(self.repo)

        self.assertEqual(git(self.repo, "hash-object", "app.py"), changes["link.py"]["hash"])
        self.assertEqual(git(self.repo, "hash-object", "link.py"), changes["link.py"]["hash"])
        self.assertIsNone(changes["dangling.py"]["hash"])

    def test_a_failed_hash_object_stops_the_scan_with_a_runtime_error(self):
        (self.repo / "app.py").write_text("app v2\n")
        real_git_output = worktree_snapshot.git_output

        def fail_hash_object(root, *args):
            if args[0] == "hash-object":
                return None
            return real_git_output(root, *args)

        with (
            mock.patch.object(worktree_snapshot, "git_output", fail_hash_object),
            self.assertRaises(RuntimeError),
        ):
            worktree_snapshot.working_tree_changes(self.repo)

    @unittest.skipIf(os.geteuid() == 0, "root reads a file with no permissions")
    def test_an_unreadable_untracked_file_stops_the_scan_with_the_os_error(self):
        secret = self.repo / "secret.txt"
        secret.write_text("hidden\n")
        secret.chmod(0)
        self.addCleanup(secret.chmod, 0o644)

        with self.assertRaises(PermissionError):
            worktree_snapshot.working_tree_changes(self.repo)


if __name__ == "__main__":
    unittest.main()
