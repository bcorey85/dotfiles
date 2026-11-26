"""Tests for the scope guard of a review loop fix pass: the files outside the pass's scope that it puts back."""
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import file_backup
import review_loop_coder
import review_loop_ruled_out
import review_loop_scope_guard
import review_loop_scoped_tests
import review_loop_script
import review_loop_stray_files
import script_utils
import test_review_loop_script as loop_tests

DOC_BEFORE = "| rule | anchor |\n"
DOC_REWRITTEN = "| rule | anchor | rewritten |\n"
MOVED_PATHS = ("old.txt", "staged_rm.txt", "ren_src.txt", "ren_dst.txt")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class ScopeGuardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.out = pathlib.Path(tmp.name) / "out"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "docs" / "plans" / "shop").mkdir(parents=True)
        files = {"app.py": "x = 1\n", "docs/rule-anchors.md": DOC_BEFORE, "tests.py": "t = 1\n",
                 "docs/plans/shop/plan.md": "# Plan\n"}
        for name, text in files.items():
            (self.repo / name).write_text(text)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        (self.repo / "app.py").write_text("x = 2\n")
        review_loop_scope_guard.SCOPE_FAULTS.clear()
        self.addCleanup(review_loop_scope_guard.SCOPE_FAULTS.clear)

    def guard(self, allowed=("app.py",), has_own_guard=lambda _path: False, finding_texts=()):
        return review_loop_scope_guard.guard_pass(self.repo, self.out, "coder1", allowed, has_own_guard,
                                                  finding_texts)

    def text(self, name):
        return (self.repo / name).read_text()

    def moved_paths_status(self):
        """`git status --short` for the paths the deletion and rename test moves: the index and work tree state."""
        status = subprocess.run(["git", "status", "--short", "--", *MOVED_PATHS], cwd=self.repo,
                                capture_output=True, text=True, check=True)
        return status.stdout

    def test_a_clean_file_outside_the_scope_is_put_back_and_named(self):
        guard = self.guard()
        (self.repo / "app.py").write_text("x = 3\n")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertEqual(self.text("app.py"), "x = 3\n")
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS,
                         ["coder1 changed files outside the review scope that no finding names; the loop put them "
                          "back: docs/rule-anchors.md; the work tree bytes of the files it "
                          "was putting back are copied to " + str(self.put_back_dir())])
        self.assertIn(review_loop_scope_guard.SCOPE_FAULTS[0], review_loop_coder.coder_fault_notes())

    def test_a_clean_file_the_pass_staged_gets_its_replaced_index_blob_noted(self):
        guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        git(self.repo, "add", "docs/rule-anchors.md")

        blob = script_utils.index_entry(self.repo, "docs/rule-anchors.md").blob
        guard.undo()

        self.assertTrue(review_loop_scope_guard.SCOPE_FAULTS[0].endswith(
            "; replaced index blobs (read with `git cat-file -p` until `git gc` prunes them, two weeks by default): "
            "docs/rule-anchors.md=" + blob))

    def test_a_clean_file_the_guard_holds_no_copy_of_is_left_as_it_is_and_named(self):
        guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        with self.capped_put_back_save():
            guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertIn("coder1 changed files outside the review scope that the loop could not copy, so the change "
                      "stays: docs/rule-anchors.md", review_loop_scope_guard.SCOPE_FAULTS)
        self.assertEqual(guard.put_back_paths, set())
        put_back_note = "coder1 changed files outside the review scope that no finding names"
        self.assertFalse([fault for fault in review_loop_scope_guard.SCOPE_FAULTS if fault.startswith(put_back_note)])

    def capped_put_back_save(self):
        """A `save_files` stand-in that copies nothing into the put-back folder (its cap is 1 byte there)."""
        real_save_files = file_backup.save_files

        def capped_for_put_back(root, paths, backup_dir):
            if backup_dir == self.put_back_dir():
                return real_save_files(root, paths, backup_dir, max_file_bytes=1)
            return real_save_files(root, paths, backup_dir)

        return mock.patch.object(file_backup, "save_files", side_effect=capped_for_put_back)

    def test_a_dirty_file_the_guard_holds_no_copy_of_keeps_its_pass_text_and_is_named_as_staying(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("pass text\n")

        with self.capped_put_back_save():
            guard.undo()

        self.assertEqual(self.text("tests.py"), "pass text\n")
        self.assertEqual(guard.put_back_paths, set())
        faults = review_loop_scope_guard.SCOPE_FAULTS
        self.assertTrue(any("could not copy, so the change stays: tests.py" in fault for fault in faults))
        self.assertFalse(any("put them back:" in fault for fault in faults))

    def test_a_staged_dirty_file_the_guard_holds_no_copy_of_keeps_its_staged_change(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("pass text\n")
        git(self.repo, "add", "tests.py")
        staged_blob = script_utils.index_entry(self.repo, "tests.py").blob

        with self.capped_put_back_save():
            guard.undo()

        self.assertEqual(script_utils.index_entry(self.repo, "tests.py").blob, staged_blob)
        self.assertEqual(guard.put_back_paths, set())

    def test_a_failed_clean_files_restore_names_the_put_back_folder(self):
        guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        real_git_output = script_utils.git_output

        def restore_fails(repo, *args, **kwargs):
            if "restore" in args:
                return None
            return real_git_output(repo, *args, **kwargs)

        with mock.patch.object(review_loop_scope_guard.script_utils, "git_output", side_effect=restore_fails), \
                self.assertRaises(RuntimeError):
            guard.undo()

        faults = review_loop_scope_guard.SCOPE_FAULTS
        self.assertTrue(any(str(self.put_back_dir()) in fault for fault in faults), faults)
        self.assertTrue(any(guard.head in fault for fault in faults), faults)

    def put_back_dir(self):
        """The folder that holds the bytes the guard overwrote while it put files back."""
        return self.out / "pass-backup" / "coder1" / "put-back" / "1"

    def test_a_clean_file_the_guard_overwrites_is_copied_to_the_put_back_folder_first(self):
        guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertEqual((self.put_back_dir() / "docs/rule-anchors.md").read_text(), DOC_REWRITTEN)
        self.assertIn(str(self.put_back_dir()), review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_dirty_file_the_guard_overwrites_is_copied_to_the_put_back_folder_first(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("saved by someone else\n")

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual((self.put_back_dir() / "tests.py").read_text(), "saved by someone else\n")
        self.assertIn(str(self.put_back_dir()), review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_two_guards_of_one_role_that_put_back_the_same_file_each_keep_their_bytes(self):
        first_guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text("first pass\n")
        first_guard.undo()
        second_guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text("second pass\n")

        second_guard.undo()

        first_dir, second_dir = first_guard.put_back_dir, second_guard.put_back_dir
        self.assertNotEqual(first_dir, second_dir)
        self.assertEqual((first_dir / "docs/rule-anchors.md").read_text(), "first pass\n")
        self.assertEqual((second_dir / "docs/rule-anchors.md").read_text(), "second pass\n")

    def test_a_guard_that_kept_nothing_does_not_claim_the_put_back_folder_of_an_earlier_guard(self):
        first_guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        first_guard.undo()
        second_guard = self.guard()

        second_guard.current_step = review_loop_scope_guard.DIRTY_FILES_STEP

        self.assertTrue(first_guard.put_back_dir.exists())
        self.assertFalse(second_guard.put_back_dir.exists())
        self.assertNotIn("copied to", second_guard.not_put_back_hint())

    def test_the_files_put_back_before_a_later_step_fails_are_still_noted(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        blob = script_utils.index_entry(self.repo, "tests.py").blob
        (self.repo / "tests.py").write_text("t = 3\n")
        git(self.repo, "add", "tests.py")
        staged_blob = script_utils.index_entry(self.repo, "tests.py").blob

        index_restore_fails = mock.patch.object(review_loop_scope_guard.script_utils, "restore_index_entry",
                                                return_value=False)
        with index_restore_fails, self.assertRaises(RuntimeError):
            guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(len(review_loop_scope_guard.SCOPE_FAULTS), 2)
        self.assertIn("put them back: tests.py", review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertNotIn(staged_blob, review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertNotIn("replaced index blobs", review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertIn(f"the index entries before the pass were: tests.py={blob}",
                      review_loop_scope_guard.SCOPE_FAULTS[1])
        self.assertIn("any clean file the pass changed stays unrestored", review_loop_scope_guard.SCOPE_FAULTS[1])

    def test_a_failed_dirty_file_step_names_the_index_entries_and_clean_files_it_never_restored(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")

        with mock.patch.object(file_backup, "restore_paths", side_effect=OSError("disk full")), \
                self.assertRaises(OSError):
            guard.undo()

        fault = review_loop_scope_guard.SCOPE_FAULTS[-1]
        self.assertIn("any index entry the pass changed stays unrestored; the index entries before the pass were: "
                      "tests.py=", fault)
        unrestored_note = "any clean file the pass changed stays unrestored; its pre-pass text is in commit"
        self.assertIn(f"{unrestored_note} {guard.head}", fault)

    def test_a_first_copy_that_fails_still_names_the_folder_holding_the_bytes_it_overwrote(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")

        with mock.patch.object(file_backup, "restore_paths", side_effect=OSError("disk full")), \
                self.assertRaises(OSError):
            guard.undo()

        self.assertEqual(guard.put_back_paths, set())
        self.assertIn(f"the work tree bytes of the files it was putting back are copied to {self.put_back_dir()}",
                      review_loop_scope_guard.SCOPE_FAULTS[-1])

    def test_a_dirty_file_whose_index_entry_is_put_back_gets_its_replaced_blob_noted(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        git(self.repo, "add", "tests.py")
        blob = script_utils.index_entry(self.repo, "tests.py").blob

        guard.undo()

        self.assertIn(f"replaced index blobs (read with `git cat-file -p` until `git gc` prunes them, two weeks by "
                      f"default): tests.py={blob}", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_clean_file_changed_but_not_staged_has_no_replaced_blob_noted(self):
        guard = self.guard()
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertNotIn("replaced index blobs", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_copy_that_fails_partway_still_notes_the_files_already_put_back(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "scratch.txt").write_text("mine\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        (self.repo / "scratch.txt").write_text("theirs\n")
        real_restore = file_backup.restore_paths
        calls = []

        def second_copy_fails(backup, paths):
            calls.append(list(paths))
            if len(calls) == 2:
                raise OSError("disk full")
            return real_restore(backup, paths)

        with mock.patch.object(file_backup, "restore_paths", side_effect=second_copy_fails), \
                self.assertRaises(OSError):
            guard.undo()

        self.assertEqual(guard.put_back_paths, {calls[0][0]})
        self.assertIn(f"put them back: {calls[0][0]}", review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertIn(str(self.put_back_dir()), review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_file_the_pass_staged_or_committed_is_put_back(self):
        for step in ("add", "commit"):
            with self.subTest(step):
                guard = self.guard()
                (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
                git(self.repo, "add", "docs/rule-anchors.md")
                if step == "commit":
                    git(self.repo, "commit", "-qm", "fix")

                guard.undo()

                self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)

    def test_a_deleted_file_outside_the_scope_is_put_back(self):
        guard = self.guard()
        (self.repo / "tests.py").unlink()

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def test_a_deletion_or_rename_made_before_the_pass_stays_and_is_not_blamed(self):
        for name in ("old.txt", "staged_rm.txt", "ren_src.txt"):
            (self.repo / name).write_text(f"{name}\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "more files")
        (self.repo / "old.txt").unlink()
        git(self.repo, "rm", "-q", "staged_rm.txt")
        git(self.repo, "mv", "ren_src.txt", "ren_dst.txt")
        index_before = self.moved_paths_status()
        guard = self.guard()
        (self.repo / "app.py").write_text("x = 3\n")

        guard.undo()

        for name in ("old.txt", "staged_rm.txt", "ren_src.txt"):
            self.assertFalse((self.repo / name).exists(), name)
        self.assertEqual(self.moved_paths_status(), index_before)
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_dirty_file_outside_the_scope_returns_to_its_text_before_the_pass(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "scratch.txt").write_text("mine\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        (self.repo / "scratch.txt").write_text("theirs\n")

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(self.text("scratch.txt"), "mine\n")
        self.assertIn("scratch.txt, tests.py", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_dirty_file_the_pass_staged_gets_its_index_entry_back(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        git(self.repo, "add", "tests.py")

        guard.undo()

        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, capture_output=True,
                                text=True, check=True)
        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(staged.stdout, "")

    def test_an_untracked_file_the_pass_staged_leaves_the_index(self):
        (self.repo / "scratch.txt").write_text("mine\n")
        guard = self.guard()
        git(self.repo, "add", "scratch.txt")

        guard.undo()

        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, capture_output=True,
                                text=True, check=True)
        self.assertEqual(staged.stdout, "")
        self.assertEqual(self.text("scratch.txt"), "mine\n")

    def test_a_file_a_finding_names_stays_changed(self):
        findings = ["- `app.py:1` the test in tests.py asserts the old value",
                    f"full check failed, failing lines:\n  File \"{self.repo}/docs/rule-anchors.md\", line 1"]
        guard = self.guard(finding_texts=findings)
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_longer_path_in_a_finding_names_no_shorter_one(self):
        guard = self.guard(finding_texts=["- `pkg/tests.py:1` wrong"])
        (self.repo / "tests.py").write_text("t = 2\n")

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def test_a_new_file_and_a_file_with_its_own_guard_stay(self):
        guard = self.guard(has_own_guard=lambda path: path.startswith("docs/plans/"))
        (self.repo / "new_test.py").write_text("n = 1\n")
        (self.repo / "docs/plans/shop/plan.md").write_text("# Plan\n\nchanged\n")

        guard.undo()

        self.assertEqual(self.text("new_test.py"), "n = 1\n")
        self.assertEqual(self.text("docs/plans/shop/plan.md"), "# Plan\n\nchanged\n")
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_guard_failure_after_a_failed_coder_call_is_a_coder_call_error_that_keeps_the_coder_message(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        undo_fails = mock.patch.object(scope_guard, "undo", side_effect=RuntimeError("scope guard: restore failed"))
        model_died = review_loop_coder.ModelCallError("model died")
        model_dies = mock.patch.object(review_loop_coder, "claude_call", side_effect=model_died)
        with undo_fails, model_dies, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("model died", str(raised.exception))
        self.assertIn("scope guard: restore failed", str(raised.exception))

    def edit_doc_then(self, outcome):
        """A coder call stand-in that rewrites a file outside the scope, then returns or raises `outcome`."""
        def model_call(*_args, **_kwargs):
            (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return mock.patch.object(review_loop_coder, "claude_call", side_effect=model_call)

    def test_a_failed_coder_call_puts_the_stray_back_and_runs_no_gate(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        scope_guard.gate_passes = lambda: self.fail("the gate ran on a failed pass")
        with self.edit_doc_then(review_loop_coder.ModelCallError("model died")), \
                self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("model died", str(raised.exception))
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIsNone(scope_guard.stray_blocker)

    def test_a_pass_guard_failure_puts_the_stray_back_and_runs_no_gate(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        scope_guard.gate_passes = lambda: self.fail("the gate ran after the pass guard failed")
        pass_guard_fails = mock.patch.object(pass_guard, "undo", side_effect=RuntimeError("pass guard failed"))
        with self.edit_doc_then("Fixed 1."), pass_guard_fails, \
                self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("pass guard failed", str(raised.exception))
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIsNone(scope_guard.stray_blocker)

    def test_a_guard_failure_after_a_finished_coder_call_is_a_coder_call_error_naming_the_failure(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        undo_fails = mock.patch.object(scope_guard, "undo", side_effect=RuntimeError("scope guard: restore failed"))
        model_works = mock.patch.object(review_loop_coder, "claude_call", return_value="Fixed 1.")
        with undo_fails, model_works, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("scope guard: restore failed", str(raised.exception))
        self.assertFalse(raised.exception.died)

    def test_an_os_error_while_undoing_a_finished_coder_call_is_a_coder_call_error(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        real_restore = file_backup.restore_paths

        def scope_backup_disk_full(backup, paths):
            if backup is scope_guard.backup:
                raise OSError("disk full")
            return real_restore(backup, paths)

        def model_edits_app(*_args, **_kwargs):
            (self.repo / "app.py").write_text("x = 9\n")
            return "Fixed 1."

        disk_full = mock.patch.object(file_backup, "restore_paths", side_effect=scope_backup_disk_full)
        model_works = mock.patch.object(review_loop_coder, "claude_call", side_effect=model_edits_app)
        with disk_full, model_works, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("disk full", str(raised.exception))
        self.assertIn("during the pass", str(raised.exception))
        self.assertFalse(raised.exception.died)
        self.assertNotIn("before it died", str(raised.exception))
        self.assertNotIn("undoing the pass failed", str(raised.exception))
        self.assertIn(f"the pre-pass copies of the dirty files not put back stay in {scope_guard.backup.backup_dir}",
                      review_loop_scope_guard.SCOPE_FAULTS[-1])

    def test_keeping_only_keeps_the_finished_call_wording(self):
        error = review_loop_coder.failed_call_error("disk full", ["a.py", "b.py"], died=False)

        kept = error.keeping_only(["a.py"])

        self.assertEqual(["a.py"], kept.changed)
        self.assertEqual(error.cause, kept.cause)
        self.assertIn("during the pass", str(kept))
        self.assertNotIn("before it died", str(kept))

    def test_a_failed_index_listing_at_guard_pass_raises_and_runs_no_index_removal(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        real_git_output = script_utils.git_output
        calls = []

        def listing_fails(repo, *args, **kwargs):
            calls.append(args)
            if "ls-files" in args and "--stage" in args:
                return None
            return real_git_output(repo, *args, **kwargs)

        with mock.patch.object(script_utils, "git_output", side_effect=listing_fails), self.assertRaises(RuntimeError):
            self.guard()

        self.assertFalse([args for args in calls if "rm" in args])
        self.assertFalse((self.out / review_loop_scope_guard.BACKUP_FOLDER / "coder1" / "out-of-scope").exists())

    def test_a_failed_status_listing_at_the_start_of_a_pass_raises(self):
        real_git_output = script_utils.git_output

        def status_fails(repo, *args, **kwargs):
            if "status" in args:
                return None
            return real_git_output(repo, *args, **kwargs)

        with mock.patch.object(review_loop_scope_guard.worktree_snapshot, "git_output", side_effect=status_fails), \
                self.assertRaises(RuntimeError):
            self.guard()

    def test_a_failed_head_lookup_in_a_repo_with_a_commit_raises(self):
        with mock.patch.object(script_utils, "head_commit", return_value=None), self.assertRaises(RuntimeError):
            self.guard()

    def test_a_failed_index_listing_at_undo_raises_and_restores_no_index_entry(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        real_git_output = script_utils.git_output

        def listing_fails(repo, *args, **kwargs):
            if "ls-files" in args and "--stage" in args:
                return None
            return real_git_output(repo, *args, **kwargs)

        with mock.patch.object(script_utils, "git_output", side_effect=listing_fails), \
                mock.patch.object(script_utils, "restore_index_entry") as restore, \
                self.assertRaises(RuntimeError):
            guard.undo()

        restore.assert_not_called()
        faults = review_loop_scope_guard.SCOPE_FAULTS
        self.assertEqual(len(faults), 2)
        self.assertIn("put them back: tests.py", faults[0])
        self.assertNotIn("replaced index blobs", faults[0])
        self.assertIn("the dirty files the loop could copy are back", faults[-1])

    def test_the_hint_names_no_commit_when_the_repo_has_none(self):
        guard = self.guard()
        guard.head = None

        guard.current_step = review_loop_scope_guard.INDEX_ENTRIES_STEP
        hint = guard.not_put_back_hint()
        self.assertNotIn("commit None", hint)
        self.assertIn("the index entries before the pass were:", hint)
        self.assertNotIn("stay unrestored", hint)

    def test_the_clean_files_step_hint_says_the_copied_dirty_files_are_back(self):
        guard = self.guard()
        guard.current_step = review_loop_scope_guard.CLEAN_FILES_STEP

        hint = guard.not_put_back_hint()

        self.assertIn("the dirty files the loop could copy are back", hint)
        self.assertIn(f"the pre-pass text of the clean files not put back is in commit {guard.head}", hint)

    def test_a_failed_pass_guard_undo_still_puts_back_the_out_of_scope_files(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        undo_fails = mock.patch.object(pass_guard, "undo", side_effect=RuntimeError("pass guard failed"))
        model_works = mock.patch.object(review_loop_coder, "claude_call", return_value="Fixed 1.")
        with undo_fails, model_works, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("pass guard failed", str(raised.exception))
        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(len(review_loop_scope_guard.SCOPE_FAULTS), 1)
        self.assertIn("put them back: tests.py", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_ruled_out_file_stays_as_the_coder_left_it_when_the_pass_guard_undo_fails(self):
        ruled_out = {"tests.py"}
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", ruled_out, [], [])
        run = mock.Mock(files_touched=set(), held_files=set(), ruled_out=ruled_out, later_phase_files=set())
        allowed = review_loop_script.LoopRun.pass_scope(run, {"app.py"})
        scope_guard = self.guard(allowed=allowed)
        (self.repo / "tests.py").write_text("t = 3\n")
        undo_fails = mock.patch.object(pass_guard, "undo", side_effect=RuntimeError("pass guard failed"))
        model_works = mock.patch.object(review_loop_coder, "claude_call", return_value="Fixed 1.")
        with undo_fails, model_works, self.assertRaises(review_loop_coder.CoderCallError):
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertEqual(self.text("tests.py"), "t = 3\n")
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_failed_pass_guard_undo_with_a_working_scope_guard_raises_the_original_error_unjoined(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        undo_fails = mock.patch.object(pass_guard, "undo", side_effect=RuntimeError("pass guard failed"))
        model_works = mock.patch.object(review_loop_coder, "claude_call", return_value="Fixed 1.")
        with undo_fails, model_works, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=self.guard())

        self.assertEqual(str(raised.exception), "pass guard failed")

    def test_both_guards_failing_in_the_undo_are_both_named_in_the_coder_call_error(self):
        pass_guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        scope_guard = self.guard()
        pass_fails = mock.patch.object(pass_guard, "undo", side_effect=RuntimeError("pass guard failed"))
        scope_fails = mock.patch.object(scope_guard, "undo", side_effect=RuntimeError("scope guard failed"))
        model_works = mock.patch.object(review_loop_coder, "claude_call", return_value="Fixed 1.")
        with pass_fails, scope_fails, model_works, self.assertRaises(review_loop_coder.CoderCallError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), pass_guard,
                                         scope_guard=scope_guard)

        self.assertIn("pass guard failed", str(raised.exception))
        self.assertIn("scope guard failed", str(raised.exception))

    def test_a_failed_git_restore_raises_notes_the_earlier_put_backs_and_keeps_the_backup(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        real_git_output = script_utils.git_output

        def restore_fails(repo, *args, **kwargs):
            if "restore" in args:
                return None
            return real_git_output(repo, *args, **kwargs)

        with mock.patch.object(script_utils, "git_output", side_effect=restore_fails), self.assertRaises(RuntimeError):
            guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertIn("put them back: tests.py", review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertIn(f"pre-pass text of the clean files not put back is in commit {guard.head}",
                      review_loop_scope_guard.SCOPE_FAULTS[1])
        self.assertTrue((guard.backup.backup_dir / "tests.py").exists())

    def guard_with_a_one_byte_backup_cap(self):
        real_save_files = file_backup.save_files

        def capped_save_files(root, paths, backup_dir):
            return real_save_files(root, paths, backup_dir, max_file_bytes=1)

        with mock.patch.object(file_backup, "save_files", side_effect=capped_save_files):
            return self.guard()

    def test_a_dirty_file_the_backup_could_not_copy_is_noted_only_when_the_pass_changed_it(self):
        for changed in (True, False):
            with self.subTest(changed=changed):
                review_loop_scope_guard.SCOPE_FAULTS.clear()
                (self.repo / "tests.py").write_text("t = 2\n")
                guard = self.guard_with_a_one_byte_backup_cap()
                if changed:
                    (self.repo / "tests.py").write_text("t = 3\n")

                guard.undo()

                if changed:
                    self.assertEqual(self.text("tests.py"), "t = 3\n")
                    self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS,
                                     ["coder1 changed files outside the review scope that the loop could not copy, "
                                      "so the change stays: tests.py"])
                else:
                    self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_staged_dirty_file_the_backup_could_not_copy_keeps_its_staged_change(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard_with_a_one_byte_backup_cap()
        (self.repo / "tests.py").write_text("t = 3\n")
        git(self.repo, "add", "tests.py")
        staged_blob = script_utils.index_entry(self.repo, "tests.py").blob

        guard.undo()

        self.assertEqual(script_utils.index_entry(self.repo, "tests.py").blob, staged_blob)
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS,
                         ["coder1 changed files outside the review scope that the loop could not copy, "
                          "so the change stays: tests.py"])
        self.assertEqual(guard.put_back_paths, set())

    def test_an_over_cap_dirty_file_the_pass_only_stages_gets_its_index_entry_back(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard_with_a_one_byte_backup_cap()
        entry_before = script_utils.index_entry(self.repo, "tests.py")
        git(self.repo, "add", "tests.py")

        guard.undo()

        self.assertEqual(script_utils.index_entry(self.repo, "tests.py"), entry_before)
        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertIn("tests.py", guard.put_back_paths)

    def test_a_dirty_file_the_pass_deleted_gets_its_text_before_the_pass_back(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        guard = self.guard()
        (self.repo / "tests.py").unlink()

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")

    def test_a_repo_with_no_commit_puts_back_dirty_files_and_fails_on_nothing(self):
        fresh = self.repo.parent / "fresh"
        fresh.mkdir()
        git(fresh, "init", "-q")
        (fresh / "scratch.txt").write_text("mine\n")
        guard = review_loop_scope_guard.guard_pass(fresh, self.out, "coder1", (), lambda _path: False, ())
        (fresh / "scratch.txt").write_text("theirs\n")

        guard.undo()

        self.assertEqual((fresh / "scratch.txt").read_text(), "mine\n")
        self.assertEqual(len(review_loop_scope_guard.SCOPE_FAULTS), 1)
        self.assertIn("put them back: scratch.txt", review_loop_scope_guard.SCOPE_FAULTS[0])

    # The gate's verdict on a file put back: kept when the fix needs it, else the loop stops naming it.
    def undo_with_gate(self, *verdicts):
        """Undoes a pass that rewrote docs/rule-anchors.md; the gate answers each call with the next of `verdicts`."""
        answers = list(verdicts)
        self.gate_states = []

        def gate_passes():
            self.gate_states.append(self.doc_state())
            return answers.pop(0)

        guard = self.guard()
        guard.gate_passes = gate_passes
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        guard.undo()
        return guard

    def doc_state(self):
        """The text of docs/rule-anchors.md, or None when the file is gone."""
        doc = self.repo / "docs/rule-anchors.md"
        return doc.read_text() if doc.exists() else None

    def test_a_file_the_gate_needs_is_kept_and_noted_as_needed(self):
        guard = self.undo_with_gate(False, True)

        self.assertEqual(self.gate_states, [DOC_BEFORE, DOC_REWRITTEN],
                         "the gate runs first with the file put back, then with the pass's bytes restored")
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertIsNone(guard.stray_blocker)
        self.assertIn("that the fix needs", review_loop_scope_guard.SCOPE_FAULTS[0])
        self.assertIn("the loop kept: docs/rule-anchors.md", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_file_the_gate_does_not_need_stops_the_loop_naming_the_file_and_the_saved_bytes(self):
        guard = self.undo_with_gate(True)

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIn("docs/rule-anchors.md", guard.stray_blocker)
        self.assertIn("the gate passes without it", guard.stray_blocker)
        self.assertIn(str(self.put_back_dir()), guard.stray_blocker)

    def test_a_gate_that_fails_with_the_file_and_without_it_puts_it_back_and_stops(self):
        guard = self.undo_with_gate(False, False)

        self.assertEqual(self.gate_states, [DOC_BEFORE, DOC_REWRITTEN])
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIn("the gate fails with it and without it", guard.stray_blocker)
        self.assertEqual((self.put_back_dir() / "docs/rule-anchors.md").read_text(), DOC_REWRITTEN)

    def test_a_gate_with_no_result_after_the_bytes_are_restored_puts_the_file_back_and_stops_as_no_gate_ran(self):
        guard = self.undo_with_gate(False, None)

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIn("no gate ran", guard.stray_blocker)
        self.assertNotIn("fails with it and without it", guard.stray_blocker)

    def test_no_gate_stops_the_loop_with_the_file_put_back(self):
        guard = self.undo_with_gate(None)

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIn("no gate ran", guard.stray_blocker)

    def test_a_file_the_pass_deleted_is_judged_as_gone_and_never_copied_from_the_put_back_folder(self):
        guard = self.guard()
        states = []
        answers = [False, True]

        def gate_passes():
            states.append(self.doc_state())
            return answers.pop(0)

        guard.gate_passes = gate_passes
        (self.repo / "docs/rule-anchors.md").unlink()

        guard.undo()

        self.assertEqual(states, [DOC_BEFORE, None])
        self.assertFalse(guard.failed)
        self.assertIsNone(guard.stray_blocker)
        self.assertIn("the loop kept: docs/rule-anchors.md", " ".join(review_loop_scope_guard.SCOPE_FAULTS))
        self.assertFalse((self.repo / "docs/rule-anchors.md").exists())

    def test_the_stop_text_for_a_deleted_file_says_the_pass_deleted_it_and_names_no_saved_bytes(self):
        guard = self.guard()
        guard.gate_passes = lambda: True
        (self.repo / "docs/rule-anchors.md").unlink()

        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIn("the pass deleted docs/rule-anchors.md", guard.stray_blocker)
        self.assertNotIn("kept the pass's bytes", guard.stray_blocker)

    def test_the_stop_text_for_one_deleted_and_one_edited_stray_names_both_clauses(self):
        guard = self.guard()
        guard.gate_passes = lambda: True
        (self.repo / "docs/rule-anchors.md").unlink()
        (self.repo / "tests.py").write_text("t = 2\n")

        guard.undo()

        self.assertIn("the pass deleted docs/rule-anchors.md", guard.stray_blocker)
        self.assertIn("kept the pass's bytes", guard.stray_blocker)

    def test_two_stray_files_are_both_named_with_plural_wording(self):
        guard = self.guard()
        guard.gate_passes = lambda: True
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        (self.repo / "tests.py").write_text("t = 2\n")

        guard.undo()

        self.assertIn("docs/rule-anchors.md, tests.py", guard.stray_blocker)
        self.assertIn("the gate passes without them", guard.stray_blocker)
        self.assertIn("the loop put them back", guard.stray_blocker)

    def test_two_strays_are_judged_each_alone_and_only_the_needed_one_stays(self):
        needed, spare = "docs/rule-anchors.md", "tests.py"
        guard = self.guard()
        states = []

        def gate_passes():
            states.append((self.doc_state(), self.text(spare)))
            # Fails without the doc, whatever state the other file is in; passes once the doc has the pass's bytes.
            return self.doc_state() == DOC_REWRITTEN

        guard.gate_passes = gate_passes
        (self.repo / needed).write_text(DOC_REWRITTEN)
        (self.repo / spare).write_text("t = 2\n")

        guard.undo()

        self.assertEqual(states, [(DOC_BEFORE, "t = 1\n"), (DOC_REWRITTEN, "t = 2\n"),
                                  (DOC_BEFORE, "t = 2\n"), (DOC_REWRITTEN, "t = 1\n")],
                         "all put back, all restored, then each stray alone put back")
        self.assertEqual(self.text(needed), DOC_REWRITTEN)
        self.assertEqual(self.text(spare), "t = 1\n")
        self.assertIn(f"the loop kept: {needed}", " ".join(review_loop_scope_guard.SCOPE_FAULTS))
        self.assertIn(spare, guard.stray_blocker)
        self.assertNotIn(needed, guard.stray_blocker)
        self.assertIn("the gate passes with it put back alone", guard.stray_blocker)

    def test_a_kept_file_the_pass_staged_keeps_its_replaced_index_blob_in_the_note(self):
        guard = self.guard()
        answers = [False, True]
        guard.gate_passes = lambda: answers.pop(0)
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        git(self.repo, "add", "docs/rule-anchors.md")
        staged_blob = subprocess.run(["git", "rev-parse", ":docs/rule-anchors.md"], cwd=self.repo,
                                     capture_output=True, text=True, check=True).stdout.strip()

        guard.undo()

        self.assertEqual(guard.replaced_blobs, {"docs/rule-anchors.md": staged_blob})
        self.assertIn(f"docs/rule-anchors.md={staged_blob}", " ".join(review_loop_scope_guard.SCOPE_FAULTS))

    def two_strays_with_gate(self, gate_passes):
        """Undoes a pass that rewrote two files outside the scope, judged by `gate_passes`."""
        guard = self.guard()
        guard.gate_passes = gate_passes
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        (self.repo / "tests.py").write_text("t = 2\n")
        return guard

    def test_two_strays_that_are_each_enough_alone_stop_with_a_reason_that_says_so(self):
        def gate_passes():
            return self.doc_state() == DOC_REWRITTEN or self.text("tests.py") == "t = 2\n"

        guard = self.two_strays_with_gate(gate_passes)
        guard.undo()

        self.assertIn("the gate fails without all of them but passes with any one of them put back",
                      guard.stray_blocker)
        self.assertNotIn("the gate passes without them", guard.stray_blocker)
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def three_strays_with_gate(self, gate_passes):
        """Undoes a pass that rewrote three files outside the scope, judged by `gate_passes`."""
        (self.repo / "extra.py").write_text("e = 1\n")
        git(self.repo, "add", "extra.py")
        git(self.repo, "commit", "-qm", "extra")
        guard = self.guard()
        guard.gate_passes = gate_passes
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "extra.py").write_text("e = 2\n")
        return guard

    def test_three_strays_where_one_is_needed_and_either_other_is_enough_say_each_alone_in_both_notes(self):
        # Needs the doc, and tests.py or extra.py; each judged with the other two restored, so only the doc is needed.
        answers = [False, True, False, True, True]
        guard = self.three_strays_with_gate(lambda: answers.pop(0))
        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertEqual(self.text("tests.py"), "t = 1\n")
        self.assertEqual(self.text("extra.py"), "e = 1\n")
        self.assertIn("the gate passes with each of them put back alone", guard.stray_blocker)
        self.assertNotIn("the gate passes without", guard.stray_blocker)
        kept_note = " ".join(review_loop_scope_guard.SCOPE_FAULTS)
        self.assertIn("fails with each of them put back alone and passes with every stray restored", kept_note)

    def test_three_strays_are_judged_with_the_other_two_restored_so_a_pair_needed_together_both_stay(self):
        def gate_passes():
            # Needs the doc and tests.py together; extra.py is spare.
            return self.doc_state() == DOC_REWRITTEN and self.text("tests.py") == "t = 2\n"

        guard = self.three_strays_with_gate(gate_passes)
        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(self.text("extra.py"), "e = 1\n")
        self.assertIn("extra.py", guard.stray_blocker)
        self.assertNotIn("tests.py", guard.stray_blocker)

    def test_two_strays_with_no_gate_result_for_the_one_at_a_time_run_stop_as_no_gate_ran(self):
        answers = [False, True, None]
        guard = self.two_strays_with_gate(lambda: answers.pop(0))
        guard.undo()

        self.assertIn("no gate ran with them put back one at a time", guard.stray_blocker)
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def test_a_gate_that_raises_on_a_later_one_at_a_time_run_names_the_strays_holding_the_pass_bytes(self):
        calls = []

        def gate_passes():
            calls.append(1)
            if len(calls) == 3:
                raise OSError("gate crashed")
            return len(calls) == 2

        guard = self.two_strays_with_gate(gate_passes)
        with self.assertRaises(OSError):
            guard.undo()

        faults = " ".join(review_loop_scope_guard.SCOPE_FAULTS)
        self.assertIn("were being judged by the gate", faults)
        self.assertNotIn("not put back is in commit", faults)

    def test_a_gate_that_raises_while_judging_notes_which_files_were_copied_back(self):
        guard = self.guard()
        calls = []

        def gate_passes():
            calls.append(1)
            if len(calls) == 1:
                return False
            raise OSError("gate crashed")

        guard.gate_passes = gate_passes
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        with self.assertRaises(OSError):
            guard.undo()

        faults = " ".join(review_loop_scope_guard.SCOPE_FAULTS)
        self.assertIn("were being judged by the gate", faults)
        self.assertIn("copied back to the work tree before the failure: docs/rule-anchors.md", faults)
        self.assertNotIn("not put back is in commit", faults)

    def test_an_undo_with_no_judging_puts_files_back_and_runs_no_gate(self):
        guard = self.guard()
        guard.gate_passes = lambda: self.fail("the gate ran on a failed pass")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo(judge=False)

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertIsNone(guard.stray_blocker)

    def test_a_pass_that_changed_nothing_outside_its_scope_runs_no_gate(self):
        guard = self.guard()
        guard.gate_passes = lambda: self.fail("the gate ran with nothing put back")
        (self.repo / "app.py").write_text("x = 3\n")

        guard.undo()

        self.assertIsNone(guard.stray_blocker)


class StubLoop(review_loop_scoped_tests.ScopedTestRuns, review_loop_stray_files.StrayFiles):
    """The host of the stray-file gate: the attributes it reads, and a canned scoped run."""

    def __init__(self, gate_commands, run):
        self.gate_commands = gate_commands
        self.repo = "repo"
        self.run = run
        self.pre_existing = False
        self.commands_run = []

    def reviewed_and_touched_files(self):
        return ["app.py"]

    def scoped_run_within(self, commands, deadline):
        self.commands_run.append(commands)
        return self.run

    def scoped_failures_pre_existing(self, real_failures):
        return self.pre_existing


class StrayGateTest(unittest.TestCase):
    def scoped_run(self, **fields):
        values = {"result": "", "tails": [], "real_failures": [], "summaries": [], "unnamed_lines": [],
                  "gave_no_result": False, "ran_nothing": False}
        return review_loop_script.coder_gate.ScopedRun(**{**values, **fields})

    def test_each_scoped_run_verdict_maps_to_the_gate_answer(self):
        red = {"tails": ["tail"], "real_failures": [("cmd", "exit 1", "out")]}
        cases = [
            ("a green run", self.scoped_run(), False, True),
            ("a red run", self.scoped_run(**red), False, False),
            ("a red run whose every failure also fails on the base tree", self.scoped_run(**red), True, True),
            ("a run that gave no result", self.scoped_run(gave_no_result=True), False, None),
            ("a run whose commands were all skipped", self.scoped_run(ran_nothing=True), False, None),
        ]
        for label, run, pre_existing, expected in cases:
            with self.subTest(label):
                loop = StubLoop(["cmd"], run)
                loop.pre_existing = pre_existing
                self.assertEqual(loop.stray_gate_passes(), expected, label)

    def test_a_red_run_with_a_refused_accepted_failures_store_gives_no_verdict(self):
        red = {"tails": ["tail"], "real_failures": [("cmd", "exit 1", "out")]}
        loop = StubLoop(["cmd"], self.scoped_run(**red))
        refused = review_loop_stray_files.accepted_failures.AcceptRefusedError("store damaged")
        with mock.patch.object(loop, "scoped_failures_pre_existing", side_effect=refused):
            self.assertIsNone(loop.stray_gate_passes())

    def test_with_no_gate_commands_the_derived_commands_for_the_touched_files_run(self):
        loop = StubLoop([], self.scoped_run())
        patch_derived = mock.patch.object(
            review_loop_scoped_tests, "derived_test_commands", return_value=["pytest app"]
        )
        with patch_derived as derived:
            self.assertTrue(loop.stray_gate_passes())

        self.assertEqual(loop.commands_run, [["pytest app"]])
        self.assertEqual(derived.call_args.args, ("repo", ["app.py"]))

    def test_with_no_gate_and_nothing_derived_no_gate_runs(self):
        loop = StubLoop([], self.scoped_run())
        with mock.patch.object(review_loop_scoped_tests, "derived_test_commands", return_value=[]):
            self.assertIsNone(loop.stray_gate_passes())

        self.assertEqual(loop.commands_run, [])


REPAIR_HUNK = "other = 1\n"


class ScopeGuardLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def fix_with_notes_edit(self, gate_command=None):
        """Runs the loop on a fix pass that also reflows notes.py, which no finding names."""
        if gate_command:
            self.gate_commands = [gate_command]
        return self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

    def test_a_stray_file_the_gate_does_not_need_stops_the_loop_and_the_packet_names_file_and_folder(self):
        completed = self.fix_with_notes_edit("grep -q 'limit = 20' app.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("notes.py", packet["blockers"][0])
        self.assertIn("the gate passes without it", packet["blockers"][0])
        self.assertIn("app.py", packet["files_touched"])
        self.assertTrue(packet["findings_remaining"], "the findings stay open")
        backup_root = self.state_dir / "loop-script" / loop_tests.AGENT_ID / "pass-backup"
        [put_back_dir] = backup_root.glob("*/put-back/1")
        self.assertIn(str(put_back_dir), packet["blockers"][0])
        self.assertIn(str(put_back_dir), packet["tool_fault"])
        self.assertEqual((put_back_dir / "notes.py").read_text(), loop_tests.NOTES_REFLOWED)

    def test_a_stray_file_with_no_gate_to_judge_it_stops_the_loop(self):
        completed = self.fix_with_notes_edit()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("no gate ran", packet["blockers"][0])

    def test_a_stray_file_the_gate_needs_stays_and_counts_as_touched(self):
        completed = self.fix_with_notes_edit("grep -q '\"a\": 1' notes.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_REFLOWED)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("notes.py", packet["files_touched"])
        self.assertIn("that the fix needs", packet["tool_fault"])
        self.assertIn("notes.py", packet["tool_fault"])

    def test_a_fix_pass_edit_outside_the_review_diff_is_put_back_and_the_packet_names_it(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        self.assertEqual((self.repo / "app.py").read_text(), loop_tests.APP_FIXED)
        _, packet = self.stored_packet()
        self.assertIn("coder1 changed files outside the review scope that no finding names; the loop put them back: "
                      "notes.py", packet["tool_fault"])
        self.assertNotIn("notes.py", packet["files_touched"])

    def test_a_file_an_earlier_round_fixed_is_kept_when_a_later_coder_edits_it_again(self):
        notes_review = loop_tests.FIX_REVIEW.replace("`app.py:2`", "`notes.py:1`")
        notes_second = 'value = {"a": 1, "b": 3}\n'
        completed = self.run_script({
            "code-reviewer": [{"result": notes_review}, {"result": loop_tests.FIX_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}, {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"notes.py": loop_tests.NOTES_REFLOWED}},
                      {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": notes_second}}],
            "closure": [{"result": loop_tests.CLOSED}, {"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), notes_second)
        _, packet = self.stored_packet()
        self.assertNotIn("notes.py", packet.get("tool_fault", ""))

    # This test walks the class-closure repair pass.
    def test_a_class_closure_repair_keeps_the_hunk_of_a_file_an_earlier_fix_changed(self):
        notes_review = loop_tests.FIX_REVIEW.replace("`app.py:2`", "`notes.py:1`")
        completed = self.run_script({
            "code-reviewer": [{"result": notes_review}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"notes.py": loop_tests.NOTES_REFLOWED}},
                      {"result": "Closed the class.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED + REPAIR_HUNK}}],
            "closure": [{"result": '{"receipt": "one site left", "open": ["app.py:4 - same limit - fix it"]}'}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_calls = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_calls), 2, "the class-closure repair ran")
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_REFLOWED + REPAIR_HUNK,
                         "the later pass's put-back leaves both the earlier fix's hunk and the repair's own")
        _, packet = self.stored_packet()
        self.assertEqual({"notes.py", "app.py"} - set(packet["files_touched"]), set())
        self.assertNotIn("put them back", packet.get("tool_fault", ""))
        self.assertNotEqual(packet["status"], "critical-blocker")

    def test_an_approval_only_finding_is_not_kept_open_when_a_stray_file_stops_the_loop(self):
        claude_md_review = loop_tests.FIX_REVIEW.replace("`app.py:2`", "`CLAUDE.md:1`")
        self.gate_commands = ["grep -q value notes.py"]
        completed = self.run_script({
            "code-reviewer": [{"result": claude_md_review}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"CLAUDE.md": "# Rules\n", "notes.py": loop_tests.NOTES_REFLOWED}}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertIn("notes.py", packet["blockers"][0])
        self.assertEqual(packet["findings_remaining"], [], "the reverted approval-only finding is an ask, not open")
        self.assertEqual([(entry["file_line"], entry.get("user_only")) for entry in packet["ask"]],
                         [("CLAUDE.md:1", True)])

    def test_a_later_phase_file_a_coder_edits_is_left_for_the_later_phase_stop_not_put_back(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
        }, header_extra="later-phase files: notes.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertIn("edited files the plan gives to a later phase: notes.py", packet["blockers"][0])
        self.assertNotIn("notes.py", packet.get("tool_fault", ""))

    def test_a_ruled_out_file_a_coder_edits_is_put_back_and_noted_once(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra="ruled-out files: notes.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        _, packet = self.stored_packet()
        self.assertNotIn("no finding names", packet.get("tool_fault", ""))

    def test_a_held_file_a_coder_edits_is_left_alone_not_put_back_by_the_scope_guard(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra=loop_tests.SCOPED_WITH_NOTES_HELD + "held files: notes.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_REFLOWED)
        _, packet = self.stored_packet()
        self.assertNotIn("no finding names", packet.get("tool_fault", ""))


if __name__ == "__main__":
    unittest.main()
