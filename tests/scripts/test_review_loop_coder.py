"""Tests for the untracked-file guard around the review loop's model calls: which untracked files a call may delete."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_calls
import review_loop_coder
import review_loop_ruled_out
import review_loop_untracked
import test_review_loop_script as loop_tests


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
        review_loop_untracked.UNTRACKED_FAULTS.clear()
        review_loop_untracked.LOOP_WRITTEN.clear()
        review_loop_calls.CALLS.clear()
        self.addCleanup(review_loop_untracked.UNTRACKED_FAULTS.clear)
        self.addCleanup(review_loop_untracked.LOOP_WRITTEN.clear)
        self.addCleanup(review_loop_calls.CALLS.clear)

    def fake_model(self, action):
        """Patches the model process with a stand-in that runs `action(repo)` and replies `done`."""
        def run_process(*_args, **_kwargs):
            action(self.repo)
            return 0, json.dumps({"result": "done", "usage": {}}), ""

        return mock.patch.multiple(review_loop_calls.script_utils, run_process=run_process,
                                   preloaded_skills_prompt=lambda _agent: "")

    def call(self, role, action):
        """Runs coder_call with a stand-in model process that runs `action(repo)`."""
        with self.fake_model(action):
            guard = review_loop_ruled_out.begin_pass(self.repo, self.out, role, set(), [], [])
            return review_loop_coder.coder_call(role, "prompt", self.repo, self.out, set(), guard)

    def coder_model_sent(self, **coder_kwargs):
        """The model coder_call hands to claude_call."""
        guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        with mock.patch.object(review_loop_coder, "claude_call", return_value="done") as fake_call:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), guard, **coder_kwargs)
        return fake_call.call_args.kwargs["model"]

    def test_coder_call_passes_the_model_to_the_model_call(self):
        self.assertEqual(self.coder_model_sent(model="haiku"), "haiku")

    def test_an_empty_coder_model_leaves_the_model_unset(self):
        self.assertIsNone(self.coder_model_sent(model=""))
        self.assertIsNone(self.coder_model_sent())

    def test_a_file_an_earlier_call_made_stays_deleted_with_no_fault_note(self):
        self.call("coder1", lambda repo: (repo / "dup.py").write_text("dup\n"))
        self.call("coder2", lambda repo: (repo / "dup.py").unlink())

        self.assertFalse((self.repo / "dup.py").exists())
        self.assertEqual(review_loop_untracked.UNTRACKED_FAULTS, [])
        self.assertNotIn("dup.py", review_loop_untracked.LOOP_WRITTEN)

    def test_a_file_a_failed_call_made_stays_deleted_with_no_fault_note(self):
        def write_then_die(repo):
            (repo / "dup.py").write_text("dup\n")
            raise RuntimeError("coder died")

        with self.assertRaises(RuntimeError):
            self.call("coder1", write_then_die)
        self.call("coder2", lambda repo: (repo / "dup.py").unlink())

        self.assertFalse((self.repo / "dup.py").exists())
        self.assertEqual(review_loop_untracked.UNTRACKED_FAULTS, [])

    def test_a_file_that_existed_before_the_loop_is_restored_with_the_fault_note(self):
        (self.repo / "mine.py").write_text("mine\n")
        self.call("coder1", lambda repo: (repo / "mine.py").unlink())

        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")
        self.assertEqual(len(review_loop_untracked.UNTRACKED_FAULTS), 1)
        self.assertIn("mine.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_a_file_that_appears_between_calls_without_a_coder_is_restored(self):
        self.call("coder1", lambda repo: (repo / "app.py").write_text("x = 2\n"))
        (self.repo / "theirs.py").write_text("theirs\n")
        self.call("coder2", lambda repo: (repo / "theirs.py").unlink())

        self.assertEqual((self.repo / "theirs.py").read_text(), "theirs\n")
        self.assertEqual(len(review_loop_untracked.UNTRACKED_FAULTS), 1)
        self.assertIn("theirs.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_every_kind_of_model_call_restores_a_deleted_file_and_names_the_call(self):
        roles = ["review1-reviewer", "disposition", "class-closure", "class-closure-retry"]
        for role in roles:
            with self.subTest(role):
                review_loop_untracked.UNTRACKED_FAULTS.clear()
                (self.repo / "mine.py").write_text("mine\n")

                with self.fake_model(lambda repo: (repo / "mine.py").unlink()):
                    review_loop_calls.claude_call(role, "prompt", self.repo, self.out)

                self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")
                self.assertEqual(len(review_loop_untracked.UNTRACKED_FAULTS), 1)
                note = review_loop_untracked.UNTRACKED_FAULTS[0]
                self.assertRegex(note, rf"call-\d\d-{role} deleted untracked files")
                self.assertIn("mine.py", note)

    def test_a_call_that_dies_after_deleting_a_file_still_restores_it_and_names_the_role(self):
        (self.repo / "mine.py").write_text("mine\n")

        def delete_then_die(repo):
            (repo / "mine.py").unlink()
            raise OSError("process broke")

        with self.fake_model(delete_then_die), self.assertRaises(OSError):
            review_loop_calls.claude_call("review1-reviewer", "prompt", self.repo, self.out)

        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")
        self.assertIn("review1-reviewer deleted untracked files", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_a_call_that_is_interrupted_after_deleting_a_file_still_restores_it(self):
        (self.repo / "mine.py").write_text("mine\n")

        def delete_then_interrupt(repo):
            (repo / "mine.py").unlink()
            raise KeyboardInterrupt

        with self.fake_model(delete_then_interrupt), self.assertRaises(KeyboardInterrupt):
            review_loop_calls.claude_call("review1-reviewer", "prompt", self.repo, self.out)

        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")

    def test_a_file_the_guard_could_not_copy_stays_gone_and_the_note_says_so(self):
        (self.repo / "big.bin").write_text("too big\n")
        # save_files binds its cap as a default argument, so the begin call is what must see the patched cap.
        original = review_loop_untracked.file_backup.save_files

        def small_cap(repo, paths, backup_dir, **kwargs):
            return original(repo, paths, backup_dir, **{**kwargs, "max_file_bytes": 1})

        with mock.patch.object(review_loop_untracked.file_backup, "save_files", small_cap):
            self.call("coder1", lambda repo: (repo / "big.bin").unlink())

        self.assertFalse((self.repo / "big.bin").exists())
        note = review_loop_untracked.UNTRACKED_FAULTS[0]
        self.assertIn("could not copy", note)
        self.assertIn("big.bin", note)

    def test_a_held_untracked_file_a_call_deletes_is_put_back_and_noted(self):
        (self.repo / "held.py").write_text("held\n")

        self.call("coder1", lambda repo: (repo / "held.py").unlink())

        self.assertEqual((self.repo / "held.py").read_text(), "held\n")
        self.assertIn("held.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_two_guards_open_at_once_keep_separate_backups(self):
        (self.repo / "mine.py").write_text("mine\n")
        first = review_loop_untracked.begin(self.repo, self.out)
        second = review_loop_untracked.begin(self.repo, self.out)

        first.restore()
        (self.repo / "mine.py").unlink()
        removal = second.restore()

        self.assertEqual(removal.restored, ["mine.py"])
        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")

    def test_a_restored_script_keeps_its_exec_bit(self):
        script = self.repo / "run.sh"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)

        self.call("coder1", lambda repo: (repo / "run.sh").unlink())

        self.assertTrue(script.stat().st_mode & 0o100)

    def test_a_one_megabyte_file_a_coder_deletes_is_restored_and_the_backup_folder_is_cleared(self):
        content = "x" * (1024 * 1024)
        (self.repo / "big.txt").write_text(content)

        self.call("coder1", lambda repo: (repo / "big.txt").unlink())

        self.assertEqual((self.repo / "big.txt").read_text(), content)
        backup_root = self.out / review_loop_untracked.BACKUP_FOLDER
        self.assertEqual(list(backup_root.iterdir()), [])


LIB_BEFORE = "a = 1\n"
LIB_AFTER_EDIT = "a = 2\n"
RULED_OUT_REASON = "the user ruled the file out of scope"
RULED_OUT_REVIEWER_LINE = "Out of scope by the user's ruling; file no finding on them: created.py, notes.py"
RULED_OUT_CODER_LINE = ("The user ruled these files out of scope. Never edit, create or delete them: "
                        "created.py, notes.py")
NOTES_FINDING = "## Fix\n- `notes.py:1` the keys are out of order\n\n"
DELETE_FINDING = ("## Fix\n- `app.py:2` the limit is wrong for `limit`; delete lib.py, nothing calls it\n\n"
                  "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")


class RuledOutLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    """The harness of test_review_loop_script.py: a stand-in `claude` answers each call from a canned scenario."""

    def setUp(self):
        super().setUp()
        self.commit_files({"lib.py": LIB_BEFORE})
        (self.repo / "lib.py").write_text(LIB_AFTER_EDIT)

    def run_loop(self, review, coder, header="ruled-out files: notes.py, created.py\n", extra_reviewers=None):
        scenario = {
            "code-reviewer": [{"result": review}, *[{"result": loop_tests.CLEAN_REVIEW}] * 3],
            "coder": [coder],
            "closure": [{"result": loop_tests.CLOSED}],
            **(extra_reviewers or {}),
        }
        completed = self.run_script(scenario, header_extra=header)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        return packet

    def test_a_ruled_out_file_a_coder_edits_or_creates_is_put_back_and_noted(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED,
                                                 "created.py": "x = 1\n"}}

        packet = self.run_loop(loop_tests.FIX_REVIEW, coder)

        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        self.assertFalse((self.repo / "created.py").exists())
        self.assertEqual(packet["files_touched"], ["app.py"])
        self.assertIn("changed files the user ruled out of scope; the loop put them back: created.py, notes.py",
                      packet["tool_fault"])

    def test_the_coder_and_reviewer_prompts_list_the_ruled_out_files(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}

        self.run_loop(loop_tests.FIX_REVIEW, coder)

        calls = self.fake_calls()
        coder_calls = [call for call in calls if call["key"] == "coder"]
        reviewer_calls = [call for call in calls if call["key"] == "code-reviewer"]
        self.assertTrue(coder_calls, "no coder call was logged")
        self.assertTrue(reviewer_calls, "no reviewer call was logged")
        for call in coder_calls:
            self.assertIn(RULED_OUT_CODER_LINE, call["prompt"])
        for call in reviewer_calls:
            self.assertIn(RULED_OUT_REVIEWER_LINE, call["prompt"])

    def test_a_ruled_out_file_the_coder_deletes_is_restored_and_noted(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["notes.py"]}

        packet = self.run_loop(loop_tests.FIX_REVIEW, coder)

        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        self.assertIn("the loop put them back: notes.py", packet["tool_fault"])

    def test_a_finding_that_only_locates_a_diff_file_does_not_allow_its_deletion(self):
        review = loop_tests.FIX_REVIEW.replace("## Ask", "- `lib.py:1` remove the unused import\n\n## Ask", 1)
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["lib.py"]}

        packet = self.run_loop(review, coder)

        self.assertEqual((self.repo / "lib.py").read_text(), LIB_AFTER_EDIT)
        self.assertIn("the loop restored lib.py", packet["tool_fault"])

    def test_a_finding_on_a_ruled_out_file_goes_to_skipped_fp_and_never_to_the_coder(self):
        review = loop_tests.FIX_REVIEW.replace("## Ask", NOTES_FINDING.removeprefix("## Fix\n") + "## Ask", 1)
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}

        packet = self.run_loop(review, coder)

        issues = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("## Issues", issues)
        self.assertIn("Files in scope:", issues)
        sent = issues.partition("## Issues")[2].partition("Files in scope:")[0]
        self.assertIn("app.py:2", sent)
        self.assertNotIn("notes.py:1", sent)
        self.assertEqual([entry["file_line"] for entry in packet["skipped_fp"]], ["notes.py:1"])
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [RULED_OUT_REASON])

    def test_a_diff_file_the_coder_deletes_with_no_finding_naming_it_is_restored_and_noted(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["lib.py"]}

        packet = self.run_loop(loop_tests.FIX_REVIEW, coder)

        self.assertEqual((self.repo / "lib.py").read_text(), LIB_AFTER_EDIT)
        self.assertIn("with no finding that names the deletion; the loop restored lib.py", packet["tool_fault"])

    def test_a_deletion_named_for_another_path_does_not_allow_the_deletion(self):
        for finding_text in ("remove data.py", "delete lib/lib.py"):
            with self.subTest(finding_text):
                self.assertFalse(review_loop_ruled_out.names_deletion([finding_text], "lib.py", "/repo"))

    def test_a_named_deletion_is_found_with_a_closing_period_or_an_absolute_path(self):
        cases = ["delete lib.py.", "delete /repo/lib.py", "lib.py is removed", "remove the file `lib.py`, unused"]
        for finding_text in cases:
            with self.subTest(finding_text):
                self.assertTrue(review_loop_ruled_out.names_deletion([finding_text], "lib.py", "/repo"))
        self.assertFalse(review_loop_ruled_out.names_deletion(["delete lib.py.bak"], "lib.py", "/repo"))

    def test_a_ruled_out_file_in_a_removed_folder_is_put_back(self):
        (self.repo / "sub").mkdir()
        self.commit_files({"sub/keys.py": "a = 1\n"})
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["sub/keys.py"]}

        packet = self.run_loop(loop_tests.FIX_REVIEW, coder, header="ruled-out files: sub/keys.py\n")

        self.assertEqual((self.repo / "sub" / "keys.py").read_text(), "a = 1\n")
        self.assertIn("the loop put them back: sub/keys.py", packet["tool_fault"])

    def test_a_diff_file_deleted_under_a_finding_that_names_the_deletion_stays_deleted(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["lib.py"]}

        packet = self.run_loop(DELETE_FINDING, coder)

        self.assertFalse((self.repo / "lib.py").exists())
        self.assertNotIn("the loop restored", packet["tool_fault"])

    def test_an_untracked_diff_file_deleted_under_a_finding_that_names_the_deletion_stays_deleted(self):
        (self.repo / "extra.py").write_text("x = 1\n")
        review = DELETE_FINDING.replace("delete lib.py", "delete extra.py")
        coder = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}, "deletes": ["extra.py"]}

        smell = {"smell-reviewer": [{"result": loop_tests.CLEAN_REVIEW}] * 3}
        packet = self.run_loop(review, coder, extra_reviewers=smell)

        self.assertFalse((self.repo / "extra.py").exists())
        self.assertNotIn("deleted untracked files", packet["tool_fault"])

    def test_a_move_or_rename_finding_counts_as_naming_the_deletion_of_the_old_path(self):
        cases = ["move lib.py to pkg/lib.py", "rename `lib.py` to core.py", "lib.py should be renamed",
                 "lib.py is moved under pkg/"]
        for finding_text in cases:
            with self.subTest(finding_text):
                self.assertTrue(review_loop_ruled_out.names_deletion([finding_text], "lib.py", "/repo"))

    def test_a_directory_a_pass_made_at_a_ruled_out_path_is_left_in_place_and_noted(self):
        review_loop_ruled_out.RULED_OUT_FAULTS.clear()
        self.addCleanup(review_loop_ruled_out.RULED_OUT_FAULTS.clear)
        guard = review_loop_ruled_out.begin_pass(self.repo, self.scratch / "guard-out", "coder1", {"keys"}, [], [])
        (self.repo / "keys").mkdir()
        (self.repo / "keys" / "a.txt").write_text("a\n")

        guard.undo()

        self.assertTrue((self.repo / "keys" / "a.txt").is_file())
        self.assertEqual(len(review_loop_ruled_out.RULED_OUT_FAULTS), 1)
        self.assertIn("keys", review_loop_ruled_out.RULED_OUT_FAULTS[0])
        self.assertIn("left in place", review_loop_ruled_out.RULED_OUT_FAULTS[0])

    def test_the_pass_backup_skips_an_untracked_file_the_untracked_guard_already_covers(self):
        (self.repo / "fresh.py").write_text("x = 1\n")
        (self.repo / "mine.py").write_text("y = 1\n")
        review_loop_untracked.LOOP_WRITTEN.add("mine.py")
        self.addCleanup(review_loop_untracked.LOOP_WRITTEN.clear)

        guard = review_loop_ruled_out.begin_pass(self.repo, self.scratch / "guard-out", "coder1", set(),
                                                 ["fresh.py", "mine.py"], [])

        self.assertEqual(guard.backup.saved, ["mine.py"])


if __name__ == "__main__":
    unittest.main()
