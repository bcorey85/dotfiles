"""Tests for the untracked-file guard around the review loop's model calls: which untracked files a call may delete."""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import finding_record
import fix_coder_written
import review_loop_calls
import review_loop_closure
import review_loop_coder
import review_loop_comment_removal
import review_loop_criteria_quotes
import review_loop_outside_writes
import review_loop_partial_fix
import review_loop_put_back
import review_loop_ruled_out
import review_loop_scope_guard
import review_loop_signoffs
import review_loop_untracked
import test_review_loop_script as loop_tests


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class FixDiffFileTest(unittest.TestCase):
    def test_an_absolute_path_still_gets_its_diff_file_under_out(self):
        with tempfile.TemporaryDirectory() as out:
            diff_file = review_loop_coder.fix_diff_file(out, "coder1", "/repo/src/a.py")

            self.assertEqual(pathlib.Path(out) / "fix-diffs" / "coder1" / "repo/src/a.py.diff", diff_file)


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
        review_loop_closure.FIX_DIFF_STATS.clear()
        self.addCleanup(review_loop_closure.FIX_DIFF_STATS.clear)
        self.addCleanup(review_loop_untracked.UNTRACKED_FAULTS.clear)
        self.addCleanup(review_loop_untracked.LOOP_WRITTEN.clear)
        self.addCleanup(review_loop_calls.CALLS.clear)
        record_writes = mock.patch.object(review_loop_outside_writes, "record_pass_writes")
        self.record_writes = record_writes.start()
        self.addCleanup(record_writes.stop)

    def no_op_scope_guard(self, role="coder1"):
        """A scope guard that owns no path: every path counts as ruled on by another guard."""
        return review_loop_scope_guard.guard_pass(self.repo, self.out, role, (), lambda _path: True, (), lambda: None)

    def fake_model(self, action):
        """Patches the model process with a stand-in that runs `action(repo)` and replies `done`."""
        def run_process(*_args, **_kwargs):
            action(self.repo)
            return 0, json.dumps({"result": "done", "usage": {}}), ""

        return mock.patch.multiple(review_loop_calls.script_utils, run_process=run_process,
                                   preloaded_skills_prompt=lambda _agent: "")

    def call(self, role, action, finding_texts=(), held=frozenset()):
        """Runs coder_call with a stand-in model process that runs `action(repo)`, and a pass guard that read
        `finding_texts`; the diff under review lists no file."""
        with self.fake_model(action):
            guard = review_loop_ruled_out.begin_pass(self.repo, self.out, role, set(), [], list(finding_texts),
                                                     held)
            return review_loop_coder.coder_call(role, "prompt", self.repo, self.out, set(held), guard,
                                                self.no_op_scope_guard(role))

    def coder_model_sent(self, **coder_kwargs):
        """The model coder_call hands to claude_call_reply."""
        guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        reply = review_loop_calls.CallReply("done", "")
        with mock.patch.object(review_loop_coder, "claude_call_reply", return_value=reply) as fake_call:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), guard,
                                         self.no_op_scope_guard(), **coder_kwargs)
        return fake_call.call_args.kwargs["model"]

    def test_coder_call_passes_the_model_to_the_model_call(self):
        self.assertEqual(self.coder_model_sent(model="haiku"), "haiku")

    def test_a_failed_model_call_raises_a_model_call_error_and_a_missing_report_is_one_too(self):
        def failing_process(*_args, **_kwargs):
            return 1, "", "boom"

        with mock.patch.multiple(review_loop_calls.script_utils, run_process=failing_process,
                                 preloaded_skills_prompt=lambda _agent: ""), \
                self.assertRaises(review_loop_calls.ModelCallError):
            review_loop_calls.claude_call("coder1", "prompt", self.repo, self.out, agent="coder")

        self.assertTrue(issubclass(review_loop_coder.NoFinalReportError, review_loop_calls.ModelCallError))

    def test_claude_call_reply_names_the_child_session_and_returns_it(self):
        commands = []

        def replying_process(command, *_args, **_kwargs):
            commands.append(command)
            return 0, json.dumps({"result": "done"}), ""

        with mock.patch.multiple(review_loop_calls.script_utils, run_process=replying_process,
                                 preloaded_skills_prompt=lambda _agent: ""):
            reply = review_loop_calls.claude_call_reply("coder1", "prompt", self.repo, self.out, agent="coder")
            text = review_loop_calls.claude_call("coder1", "prompt", self.repo, self.out, agent="coder")

        named = commands[0][commands[0].index("--session-id") + 1]
        self.assertEqual(reply, review_loop_calls.CallReply("done", named))
        self.assertEqual(text, "done")

    def test_a_call_with_no_json_reply_raises_an_error_that_carries_the_session(self):
        commands = []

        def silent_process(command, *_args, **_kwargs):
            commands.append(command)
            return None, "", ""

        with mock.patch.multiple(review_loop_calls.script_utils, run_process=silent_process,
                                 preloaded_skills_prompt=lambda _agent: ""), \
                self.assertRaises(review_loop_calls.ModelCallError) as raised:
            review_loop_calls.claude_call_reply("coder1", "prompt", self.repo, self.out, agent="coder")

        self.assertEqual(raised.exception.session, commands[0][commands[0].index("--session-id") + 1])

    def test_a_coder_failure_that_is_not_a_model_call_error_is_not_swallowed(self):
        guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
        with mock.patch.object(review_loop_coder, "claude_call_reply",
                               side_effect=RuntimeError("a git read failed")), \
                self.assertRaises(RuntimeError) as raised:
            review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), guard,
                                         self.no_op_scope_guard())

        self.assertNotIsInstance(raised.exception, review_loop_coder.CoderCallError)

    def test_an_empty_coder_model_leaves_the_model_unset(self):
        self.assertIsNone(self.coder_model_sent(model=""))
        self.assertIsNone(self.coder_model_sent())

    def test_a_file_an_earlier_call_made_stays_deleted_with_no_fault_note(self):
        self.call("coder1", lambda repo: (repo / "dup.py").write_text("dup\n"))
        self.call("coder2", lambda repo: (repo / "dup.py").unlink())

        self.assertFalse((self.repo / "dup.py").exists())
        self.assertEqual(review_loop_untracked.UNTRACKED_FAULTS, [])
        self.assertNotIn("dup.py", review_loop_untracked.LOOP_WRITTEN)

    def test_a_held_untracked_file_a_finding_names_for_deletion_is_put_back_and_noted(self):
        (self.repo / "theirs.py").write_text("theirs\n")

        self.call("coder1", lambda repo: (repo / "theirs.py").unlink(),
                  ["`app.py:1` delete theirs.py"], held={"theirs.py"})

        self.assertEqual((self.repo / "theirs.py").read_text(), "theirs\n")
        self.assertIn("theirs.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_a_held_file_the_fix_coder_record_names_is_put_back_and_noted(self):
        (self.repo / "theirs.py").write_text("theirs\n")
        fix_coder_written.add_paths(self.repo, {"theirs.py"})

        self.call("coder1", lambda repo: (repo / "theirs.py").unlink(), [], held={"theirs.py"})

        self.assertEqual((self.repo / "theirs.py").read_text(), "theirs\n")
        self.assertIn("theirs.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_an_untracked_file_a_finding_names_for_deletion_stays_deleted_when_the_diff_lists_no_such_file(self):
        (self.repo / "stray.py").write_text("stray\n")

        self.call("coder1", lambda repo: (repo / "stray.py").unlink(),
                  ["`app.py:1` delete stray.py, nothing calls it"])

        self.assertFalse((self.repo / "stray.py").exists())
        self.assertEqual(review_loop_untracked.UNTRACKED_FAULTS, [])

    def test_an_untracked_file_no_finding_names_is_restored_and_noted_when_a_finding_names_another(self):
        (self.repo / "stray.py").write_text("stray\n")
        (self.repo / "mine.py").write_text("mine\n")

        self.call("coder1", lambda repo: (repo / "mine.py").unlink(),
                  ["`app.py:1` delete stray.py, nothing calls it"])

        self.assertEqual((self.repo / "mine.py").read_text(), "mine\n")
        self.assertIn("mine.py", review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_a_file_the_fix_coder_record_names_stays_deleted_after_the_loop_state_is_lost(self):
        (self.repo / "fix_made.py").write_text("x\n")
        fix_coder_written.add_paths(self.repo, {"fix_made.py"})

        self.call("coder2", lambda repo: (repo / "fix_made.py").unlink())

        self.assertFalse((self.repo / "fix_made.py").exists())
        self.assertEqual(review_loop_untracked.UNTRACKED_FAULTS, [])

    def test_a_file_the_fix_coder_wrote_is_recorded_for_the_next_code_review_start(self):
        self.call("coder1", lambda repo: (repo / "fix_made.py").write_text("x\n"))

        self.assertEqual(fix_coder_written.recorded(self.repo), {"fix_made.py"})

    def test_a_file_a_failed_call_made_stays_deleted_with_no_fault_note(self):
        def write_then_die(repo):
            (repo / "dup.py").write_text("dup\n")
            raise review_loop_calls.ModelCallError("coder died")

        with self.assertRaises(review_loop_coder.CoderCallError):
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

    def test_a_coder_that_exits_zero_with_an_error_result_is_a_dead_pass(self):
        reply = {"is_error": True, "result": "Claude usage limit reached", "usage": {}}

        def run_process(*_args, **_kwargs):
            return 0, json.dumps(reply), ""

        with mock.patch.multiple(review_loop_calls.script_utils, run_process=run_process,
                                 preloaded_skills_prompt=lambda _agent: ""):
            guard = review_loop_ruled_out.begin_pass(self.repo, self.out, "coder1", set(), [], [])
            with self.assertRaisesRegex(review_loop_coder.CoderCallError, "usage limit reached"):
                review_loop_coder.coder_call("coder1", "prompt", self.repo, self.out, set(), guard,
                                             self.no_op_scope_guard())

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
        self.assertTrue(review_loop_ruled_out.names_deletion(["delete ./lib/x.py"], "lib/x.py", "/repo"))
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


class DeadCoderRecordTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    """A fix coder that edits a file and exits non-zero leaves a record; the next launch takes its findings."""

    FINDING = "`app.py:2` the limit is wrong for `limit`"

    def findings_header(self, *findings):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps(list(findings)))
        return f"mode: fix-first\nfindings: {findings_file}\n"

    def record_file(self):
        return self.repo / ".git" / "review-fix" / "partial-fix.json"

    def save_record(self, *findings, diff=""):
        self.record_file().parent.mkdir(parents=True, exist_ok=True)
        self.record_file().write_text(json.dumps({"findings": list(findings), "diff": diff, "time": 1}))

    def die_mid_edit(self):
        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"app.py": loop_tests.APP_FIXED}, "exit": 1}],
        }, header_extra=self.findings_header(self.FINDING))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return self.stored_packet()[1]

    def test_a_coder_that_dies_after_editing_leaves_a_record_and_the_stop_note_names_the_findings(self):
        started = time.time()
        packet = self.die_mid_edit()
        finished = time.time()

        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [self.FINDING])
        self.assertIn("-limit = 2", record["diff"])
        self.assertIn("+limit = 20", record["diff"])
        self.assertGreaterEqual(record["time"], started)
        self.assertLessEqual(record["time"], finished)
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=self.repo, capture_output=True, text=True,
                                check=True).stdout.strip()
        self.assertEqual(record["branch"], branch)
        self.assertIn(self.FINDING, packet["blockers"][0])
        self.assertIn("unverified", packet["blockers"][0])
        self.assertIn("may hold part of the fix", packet["blockers"][0])
        self.assertIn(str(self.record_file()), packet["blockers"][0])

    def test_a_coder_that_exits_zero_with_no_final_report_leaves_a_record_and_an_unverified_note(self):
        completed = self.run_script({
            "coder": [{"result": "", "edits": {"app.py": loop_tests.APP_FIXED}}],
        }, header_extra=self.findings_header(self.FINDING))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [self.FINDING])
        blocker = self.stored_packet()[1]["blockers"][0]
        self.assertIn("no final report", blocker)
        self.assertIn("unverified", blocker)

    def test_a_coder_that_dies_with_no_edits_keeps_the_findings_and_does_not_claim_a_partial_fix(self):
        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {}, "exit": 1}],
        }, header_extra=self.findings_header(self.FINDING))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        blocker = self.stored_packet()[1]["blockers"][0]
        self.assertNotIn("may hold part of the fix", blocker)
        self.assertNotIn("partial diff", blocker)
        self.assertIn(self.FINDING, blocker)
        self.assertIn(str(self.record_file()), blocker)

    def test_findings_on_a_reverted_approval_only_path_stay_out_of_the_record_and_the_note(self):
        reverted_finding = "`CLAUDE.md:1` the rule is wrong"
        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "exit": 1,
                       "edits": {"app.py": loop_tests.APP_FIXED, "CLAUDE.md": "# Rules\n"}}],
        }, header_extra=self.findings_header(self.FINDING, reverted_finding))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [self.FINDING])
        blocker = self.stored_packet()[1]["blockers"][0]
        self.assertIn(self.FINDING, blocker)
        self.assertNotIn(reverted_finding, blocker)

    def test_a_dying_coder_that_edits_only_approval_only_paths_removes_the_older_record(self):
        self.save_record("`CLAUDE.md:1` the rule is wrong")

        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(self.record_file().exists())

    def test_a_path_the_loop_fully_put_back_is_absent_from_the_record_diff(self):
        self.commit_files({"app.py": "# keep this note\n" + loop_tests.APP_BEFORE})
        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"app.py": loop_tests.APP_BEFORE}, "exit": 1}],
        }, header_extra=self.findings_header(self.FINDING))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("# keep this note", (self.repo / "app.py").read_text())
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["diff"], "")
        self.assertNotIn("may hold part of the fix", self.stored_packet()[1]["blockers"][0])

    def test_a_launch_carrying_only_a_saved_record_still_plans_the_structure_pass(self):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps([self.FINDING]))
        for header_findings, expected_skipped in (([], False), ([self.FINDING], True)):
            with self.subTest(header_findings=header_findings):
                extra = f"findings: {findings_file}" if header_findings else ""
                loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
                prompt = self.scratch / "prompt.txt"
                prompt.write_text(self.prompt_file_text(extra))
                header, handoff = loop_main.read_prompt(str(prompt))
                request = loop_main.LoopRequest(str(self.repo), self.scratch, loop_tests.SESSION, header, handoff,
                                                {"fixed": [], "files_touched": set()}, ["echo ran"],
                                                gates_every_run=True)
                self.save_record("`app.py:3` carried")
                with mock.patch.object(loop_main, "first_pass") as first_pass, \
                        mock.patch.object(loop_main, "walk"), \
                        mock.patch.object(loop_main, "write_telemetry", return_value=([], [])):
                    loop_main.run_loop(request)

                sent_findings = first_pass.call_args.args[1]
                self.assertIn("`app.py:3` carried", sent_findings)
                self.assertEqual(first_pass.call_args.args[3], expected_skipped)

    def test_the_next_launch_sends_the_recorded_findings_to_the_coder_and_removes_the_record(self):
        self.die_mid_edit()
        self.reset_fake_run()

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}],
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_prompts = [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_prompts), 1)
        self.assertIn("the limit is wrong", coder_prompts[0])
        self.assertFalse(self.record_file().exists())

    def test_a_relaunch_with_the_same_findings_removes_the_record(self):
        self.die_mid_edit()
        self.reset_fake_run()

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}],
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra=self.findings_header(self.FINDING))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(self.record_file().exists())
        coder_prompts = [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(coder_prompts[0].count("the limit is wrong"), 1)

    def test_a_relaunch_whose_saved_findings_all_sit_on_a_ruled_out_file_drops_the_record_with_no_coder(self):
        self.save_record("`notes.py:1` the keys are out of order")

        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra="ruled-out files: notes.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        self.assertFalse(self.record_file().exists())

    def test_a_settle_followed_by_a_dead_pass_writes_the_record_once(self):
        self.save_record("`notes.py:1` the keys are out of order")
        dead_finding_text = "`app.py:2` the limit is wrong for `limit`"
        loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text("ruled-out files: notes.py\n"))
        header, handoff = loop_main.read_prompt(str(prompt))
        request = loop_main.LoopRequest(str(self.repo), self.scratch, loop_tests.SESSION, header, handoff,
                                        {"fixed": [], "files_touched": set()}, ["echo ran"])

        def settle_then_die(loop, findings, *_flags):
            loop.fix_first(findings)
            snapshots = review_loop_put_back.PassSnapshots(
                review_loop_signoffs.snapshot_signoffs(self.repo, []),
                review_loop_comment_removal.snapshot_comments(self.repo, []),
                review_loop_criteria_quotes.EMPTY_AC_QUOTES)
            died = review_loop_coder.CoderCallError("the coder died", [])
            loop.failed_pass_blocker("coder0", died, snapshots, [finding_record.parse_finding(dead_finding_text)],
                                     [])

        with mock.patch.object(loop_main, "first_pass", side_effect=settle_then_die), \
                mock.patch.object(loop_main, "walk"), \
                mock.patch.object(loop_main, "write_telemetry", return_value=([], [])), \
                mock.patch.object(review_loop_partial_fix, "write_partial_fix",
                                  wraps=review_loop_partial_fix.write_partial_fix) as write_record:
            loop_main.run_loop(request)

        write_record.assert_called_once()
        self.assertEqual(json.loads(self.record_file().read_text())["findings"], [dead_finding_text])

    def test_a_settle_followed_by_an_unlisted_crash_still_removes_the_settled_record(self):
        self.save_record("`notes.py:1` the keys are out of order")
        loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text("ruled-out files: notes.py\n"))
        header, handoff = loop_main.read_prompt(str(prompt))
        request = loop_main.LoopRequest(str(self.repo), self.scratch, loop_tests.SESSION, header, handoff,
                                        {"fixed": [], "files_touched": set()}, ["echo ran"])

        def settle_then_crash(loop, findings, *_flags):
            loop.fix_first(findings)
            raise RuntimeError("the reviewer reply was an error")

        with mock.patch.object(loop_main, "first_pass", side_effect=settle_then_crash), \
                mock.patch.object(loop_main, "walk"), \
                mock.patch.object(loop_main, "write_telemetry", return_value=([], [])), \
                self.assertRaises(RuntimeError):
            loop_main.run_loop(request)

        self.assertFalse(self.record_file().exists())

    def loop_request(self, loop_main):
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text(""))
        header, handoff = loop_main.read_prompt(str(prompt))
        return loop_main.LoopRequest(str(self.repo), self.scratch, loop_tests.SESSION, header, handoff,
                                     {"fixed": [], "files_touched": set()}, ["echo ran"])

    def test_a_failed_record_save_never_masks_the_crash_that_was_in_flight(self):
        loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
        request = self.loop_request(loop_main)
        stderr = io.StringIO()

        with mock.patch.object(loop_main, "first_pass", side_effect=ValueError("the real crash")), \
                mock.patch.object(review_loop_partial_fix, "save_pending", side_effect=OSError("disk full")), \
                contextlib.redirect_stderr(stderr), \
                self.assertRaises(ValueError) as raised:
            loop_main.run_loop(request)

        self.assertEqual(str(raised.exception), "the real crash")
        self.assertIn("review-loop-script: could not save the partial-fix record: disk full", stderr.getvalue())

    def test_a_failed_record_save_with_no_crash_in_flight_still_fails_loudly(self):
        loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
        request = self.loop_request(loop_main)

        with mock.patch.object(loop_main, "first_pass"), mock.patch.object(loop_main, "walk"), \
                mock.patch.object(review_loop_partial_fix, "save_pending", side_effect=OSError("disk full")), \
                contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(OSError):
            loop_main.run_loop(request)

    def test_a_record_from_another_branch_stops_the_run_with_a_critical_blocker_naming_the_file(self):
        self.die_mid_edit()
        record = json.loads(self.record_file().read_text())
        record["branch"] = "some-other-branch"
        self.record_file().write_text(json.dumps(record))
        loop_main = loop_tests.load_script_module(loop_tests.SCRIPT.parent / "review_loop_main.py")
        request = self.loop_request(loop_main)

        with mock.patch.object(loop_main, "write_telemetry", return_value=([], [])):
            outcome = loop_main.run_loop(request)

        self.assertEqual(outcome["status"], "critical-blocker")
        self.assertIn(f"delete {self.record_file()} to drop the record", " ".join(outcome["blockers"]))

    def test_a_relaunch_whose_coder_edits_a_later_phase_file_drops_the_sent_findings_from_the_record(self):
        self.die_mid_edit()
        self.reset_fake_run()

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED,
                                                       "notes.py": loop_tests.NOTES_REFLOWED}}],
        }, header_extra="later-phase files: notes.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.stored_packet()[1]["status"], "critical-blocker")
        self.assertFalse(self.record_file().exists())

    def test_a_coder_that_dies_again_keeps_the_saved_findings_on_a_held_file_in_the_record(self):
        held_finding = "`notes.py:1` the keys are out of order"
        self.save_record(self.FINDING, held_finding)
        (self.repo / "notes.py").write_text("value = 1  # another session's edit\n")

        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"app.py": loop_tests.APP_FIXED}, "exit": 1}],
        }, header_extra=loop_tests.SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(sorted(record["findings"]), sorted([self.FINDING, held_finding]))

    def test_a_record_written_on_another_branch_stops_the_launch_and_names_both_branches(self):
        self.die_mid_edit()
        record = json.loads(self.record_file().read_text())
        record["branch"] = "some-other-branch"
        self.record_file().write_text(json.dumps(record))

        record_before = self.record_file().read_text()
        current_branch = subprocess.run(["git", "-C", str(self.repo), "branch", "--show-current"],
                                        capture_output=True, text=True, check=True).stdout.strip()
        self.reset_fake_run()

        completed = self.run_script({"coder": [{"result": "Fixed 1.", "edits": {}}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.stored_packet()[1]["status"], "critical-blocker")
        output = completed.stdout + completed.stderr
        self.assertIn(current_branch, output)
        self.assertEqual(self.fake_calls(), [])
        self.assertEqual(self.record_file().read_text(), record_before)
        self.assertIn("some-other-branch", output)
        self.assertIn(f"delete {self.record_file()} to drop the record", output)

        with self.subTest(record_written_on="a detached HEAD"):
            record["branch"] = ""
            self.record_file().write_text(json.dumps(record))
            self.reset_fake_run()

            detached = self.run_script({"coder": [{"result": "Fixed 1.", "edits": {}}]})

            self.assertEqual(detached.returncode, 0, detached.stderr)
            self.assertIn("detached HEAD", detached.stdout + detached.stderr)

    def test_a_record_written_while_git_failed_keeps_a_null_branch_apart_from_a_detached_head(self):
        with mock.patch.object(review_loop_partial_fix.script_utils, "current_branch", return_value=None):
            review_loop_partial_fix.write_partial_fix(self.repo, [self.FINDING], {}, "now")

        record = json.loads(self.record_file().read_text())
        self.assertIn("branch", record)
        self.assertIsNone(record["branch"], "a failed git call must not read back as a detached HEAD")

    def test_a_record_with_a_null_branch_launches_normally(self):
        self.die_mid_edit()
        record = json.loads(self.record_file().read_text())
        record["branch"] = None
        self.record_file().write_text(json.dumps(record))
        self.reset_fake_run()

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}],
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("detached HEAD", completed.stdout + completed.stderr)

    def test_a_gate_pass_that_dies_saves_no_record_and_the_stop_note_calls_nothing_unverified(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}] * 2,
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED, "broken.flag": "x\n"}},
                      {"result": "You've hit your limit", "edits": {"app.py": loop_tests.APP_BEFORE}, "exit": 1}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra=self.findings_header(self.FINDING), quality_check="test ! -f broken.flag")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)
        self.assertFalse(self.record_file().exists(), "a dying coder-gate pass must save no record")
        blockers = " ".join(self.stored_packet()[1]["blockers"])
        self.assertNotIn("unverified", blockers)

    def test_a_record_with_no_branch_field_launches_normally(self):
        self.save_record(self.FINDING)
        self.assertNotIn("branch", json.loads(self.record_file().read_text()))

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}],
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_prompts = [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]
        self.assertIn("the limit is wrong", coder_prompts[0])
        self.assertFalse(self.record_file().exists())

    def test_a_dying_coder_whose_sent_finding_is_reverted_keeps_the_held_saved_finding_with_no_note(self):
        reverted_finding = "`CLAUDE.md:1` the rule is wrong"
        held_finding = "`notes.py:1` the keys are out of order"
        self.save_record(held_finding)
        (self.repo / "notes.py").write_text("value = 1  # another session's edit\n")
        header = self.findings_header(reverted_finding) + loop_tests.SCOPED_WITH_NOTES_HELD

        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        }, header_extra=header)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [held_finding])
        self.assertNotIn("unverified", " ".join(self.stored_packet()[1]["blockers"]))

    def test_a_relaunch_sends_the_findings_off_held_files_and_keeps_the_held_ones_in_the_record(self):
        held_finding = "`notes.py:1` the keys are out of order"
        self.save_record(self.FINDING, held_finding)
        (self.repo / "notes.py").write_text("value = 1  # another session's edit\n")

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}],
            "code-reviewer": [{"result": loop_tests.CLEAN_REVIEW}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra=loop_tests.SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_prompts = [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_prompts), 1)
        self.assertIn("the limit is wrong", coder_prompts[0])
        self.assertNotIn("the keys are out of order", coder_prompts[0])
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [held_finding])

    def test_a_coder_that_dies_again_keeps_the_record_and_the_stop_note_names_the_findings(self):
        self.die_mid_edit()
        self.reset_fake_run()

        completed = self.run_script({
            "coder": [{"result": "You've hit your limit", "edits": {"app.py": loop_tests.APP_FIXED}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(record["findings"], [self.FINDING])
        self.assertIn(self.FINDING, self.stored_packet()[1]["blockers"][0])

    def test_a_finding_pass_that_dies_after_a_settle_replaces_the_record_with_its_own_findings(self):
        held_finding = "`notes.py:1` the keys are out of order"
        new_finding = "`app.py:4` the fourth limit is wrong"
        second_edit = loop_tests.APP_FIXED.replace("limit = 4", "limit = 40")
        new_review = loop_tests.FIX_REVIEW.replace("`app.py:2` the limit is wrong for `limit`", new_finding)
        self.save_record(self.FINDING, held_finding)
        (self.repo / "notes.py").write_text("value = 1  # another session's edit\n")

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}},
                      {"result": "You've hit your limit", "edits": {"app.py": second_edit}, "exit": 1}],
            "code-reviewer": [{"result": new_review}],
            "closure": [{"result": loop_tests.CLOSED}],
        }, header_extra=loop_tests.SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads(self.record_file().read_text())
        self.assertEqual(sorted(record["findings"]), sorted([new_finding, held_finding]))
        self.assertIn("+limit = 40", record["diff"])
        self.assertNotIn("the limit is wrong for `limit`", " ".join(record["findings"]))
        blocker = self.stored_packet()[1]["blockers"][0]
        self.assertIn(new_finding, blocker)
        self.assertIn("unverified", blocker)

    def test_a_relaunch_where_no_coder_pass_runs_keeps_the_record(self):
        self.save_record("`notes.py:1` the keys are out of order", diff="+value = 1\n")
        saved = json.loads(self.record_file().read_text())
        (self.repo / "notes.py").write_text("value = 1  # another session's edit\n")

        completed = self.run_script({}, header_extra=loop_tests.SCOPED_WITH_NOTES_HELD + "no-review: yes\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        # No finding is left to send, so the held finding stays and the diff is dropped (see the partial-fix docs).
        kept = json.loads(self.record_file().read_text())
        self.assertEqual(kept["findings"], saved["findings"])
        self.assertEqual(kept["diff"], "")

    def test_a_damaged_record_stops_the_launch_naming_the_file_and_the_expected_form(self):
        self.record_file().parent.mkdir(parents=True, exist_ok=True)
        for damaged in ("not json", "[]", '{"findings": [""]}'):
            with self.subTest(damaged=damaged):
                self.record_file().write_text(damaged)

                completed = self.run_script({})

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("critical-blocker", completed.stdout)
                self.assertIn(str(self.record_file()), completed.stdout)
                self.assertIn("non-empty finding texts", completed.stdout)


if __name__ == "__main__":
    unittest.main()
