"""A /code phase ask the session rules `rejected` is stored as a rejected ask, so the next review loop drops the
same ask raised again."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest.mock

import toolkit_paths
from test_phase_asks import ASKS, CONTEXT, GIT_ENV, SESSION, ScriptRunCase, ask

sys.path.insert(0, str(toolkit_paths.CODE_DIR))  # review_loop_ruled imports coder_report
import finding_record
import handback
import handback_store
import phase_asks
import review_asks
import review_loop_findings
import review_loop_ruled

OTHER_SESSION = "33333333-aaaa-bbbb-cccc-444444444444"
THIRD_SESSION = "55555555-aaaa-bbbb-cccc-666666666666"
FIRST_TEXT = "src/a.py:3 Should an empty list count as none?"
REVIEWER_WORDING = "`src/a.py:41` [bug] Should an empty list count as none now? — change: treat it as none"


class RejectionCase(ScriptRunCase):
    def rejected_in(self, session_id, repo=None):
        key = handback_store.ruled_rows_repo(repo or self.repo)
        return handback_store.rejected_ask_texts(session_id, key)

    def rejected_rows(self, session_id):
        return handback_store.session_rows(session_id, handback_store.ASK_REJECTED)

    def raised_again_is_dropped(self, session_id, ask_text, repo=None):
        records = review_loop_ruled.rejected_ask_records(session_id, str(repo or self.repo))
        return review_loop_findings.repeats_a_rejected_ask(finding_record.parse_finding(ask_text), records)


class RejectedAskIsRecordedTest(RejectionCase):
    def test_the_next_loop_drops_the_ask_the_phase_ruling_rejected(self):
        self.assertFalse(self.raised_again_is_dropped(SESSION, REVIEWER_WORDING))

        code, _, _ = self.run_script("rule", "rejected:the empty list is a real value", "accepted:b")

        self.assertEqual(code, 0)
        self.assertEqual(self.rejected_in(SESSION), [FIRST_TEXT])
        self.assertTrue(self.raised_again_is_dropped(SESSION, REVIEWER_WORDING))
        self.assertFalse(self.raised_again_is_dropped(SESSION, "`src/a.py:9` [bug] Should the cap be 3 or 5?"))

    def test_an_accepted_ask_writes_no_rejected_row(self):
        code, _, _ = self.run_script("rule", "accepted:a", "accepted:b")

        self.assertEqual(code, 0)
        self.assertEqual(self.rejected_rows(SESSION), [])

    def test_a_rerun_adds_no_row(self):
        self.run_script("rule", "rejected:a", "rejected:b")
        self.run_script("rule", "rejected:a", "rejected:b")

        self.assertEqual(len(self.rejected_rows(SESSION)), 2)

    def test_a_rerun_after_a_crash_between_the_rejected_row_and_the_ruled_row_adds_no_row(self):
        handback_store.record_rejected_ask(
            SESSION, FIRST_TEXT, handback_store.ruled_rows_repo(self.repo), ASKS[0]["question"])

        code, _, _ = self.run_script("rule", "rejected:a", "accepted:b")

        self.assertEqual(code, 0)
        self.assertEqual(len(self.rejected_rows(SESSION)), 1)

    def test_a_text_withdrawn_earlier_is_recorded_again(self):
        key = handback_store.ruled_rows_repo(self.repo)
        handback_store.record_rejected_ask(SESSION, FIRST_TEXT, key, "q")
        handback_store.record_rejection_withdrawn(SESSION, FIRST_TEXT, key)

        self.run_script("rule", "rejected:a", "accepted:b")

        self.assertEqual(self.rejected_in(SESSION), [FIRST_TEXT])

    def test_a_failing_logger_still_leaves_the_rejected_row(self):
        failing_claude = self.temp_root / "claude"
        logger = failing_claude / "skills/review/log-review-finding"
        logger.parent.mkdir(parents=True)
        logger.write_text("#!/usr/bin/env bash\nexit 1\n")

        code, _, errors = self.run_script("rule", "rejected:a", "accepted:b", REVIEW_FIX_CLAUDE_DIR=str(failing_claude))

        self.assertEqual(code, 0)
        self.assertIn("outcome row not logged", errors)
        self.assertEqual(self.rejected_in(SESSION), [FIRST_TEXT])

    def test_a_hanging_logger_still_leaves_the_rejected_row(self):
        hanging = self.temp_root / "hanging-logger"
        hanging.write_text("#!/usr/bin/env bash\nsleep 4\n")

        with unittest.mock.patch.object(phase_asks, "ASK_LOGGER", hanging), \
                unittest.mock.patch.object(review_asks.handback, "LOGGER_TIMEOUT_SECONDS", 1), \
                unittest.mock.patch("pathlib.Path.cwd", return_value=self.repo), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = phase_asks.command_rule(["rejected:a", "accepted:b"])

        self.assertEqual(code, 0)
        self.assertEqual(self.rejected_in(SESSION), [FIRST_TEXT])

    def test_telemetry_off_still_records_the_rejection(self):
        code, _, _ = self.run_script("rule", "rejected:a", "accepted:b", CLAUDE_TOOLKIT_TELEMETRY="0")

        self.assertEqual(code, 0)
        self.assertEqual(self.rejected_in(SESSION), [FIRST_TEXT])


class RejectedAskTextShapesTest(RejectionCase):
    def rule_one_ask(self, item):
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [item], CONTEXT, "loop-b:2")
        self.run_script("rule", "accepted:a", "accepted:b", "rejected:no")

    def test_an_ask_with_no_location_is_stored_as_its_question(self):
        item = {**ask("Which tenant owns the shard key?", "77f295856f1a9eee", 1), "file_line": handback.UNLOCATED}

        self.rule_one_ask(item)

        self.assertEqual(self.rejected_in(SESSION), ["Which tenant owns the shard key?"])
        self.assertTrue(self.raised_again_is_dropped(SESSION, "[bug] Which tenant owns the shard key? — change: x"))

    def test_quotes_newlines_and_a_long_question_are_stored_and_matched(self):
        question = 'Should "it" use \'both\'?\nSecond line `x`; $HOME ' + "y" * 20000
        item = ask(question, "88f295856f1a9eee", 5)

        self.rule_one_ask(item)

        stored = self.rejected_in(SESSION)
        self.assertEqual(stored, [review_asks.rejected_ask_text(item)])
        self.assertGreater(len(stored[0]), 20000)
        self.assertNotIn("\n", stored[0])


class SessionKeyTest(RejectionCase):
    def test_the_opener_and_the_ruler_each_hold_the_rejection_once(self):
        third_ask = ask("Should the limit be 7?", "99f295856f1a9eee", 20)
        handback_store.record_phase_asks_open(OTHER_SESSION, self.repo_top, [third_ask], CONTEXT, "loop-b:2")

        code, _, _ = self.run_script("rule", "rejected:a", "accepted:b", "rejected:c",
                                     CLAUDE_CODE_SESSION_ID=THIRD_SESSION)

        self.assertEqual(code, 0)
        expected = [FIRST_TEXT, "src/a.py:20 Should the limit be 7?"]
        for session_id in (SESSION, OTHER_SESSION, THIRD_SESSION):
            with self.subTest(session_id):
                self.assertEqual(self.rejected_in(session_id), expected)

    def test_a_session_that_is_both_opener_and_ruler_holds_one_row_per_text(self):
        self.run_script("rule", "rejected:a", "accepted:b")

        self.assertEqual(len(self.rejected_rows(SESSION)), 1)


class ConcurrentRejectionTest(RejectionCase):
    def test_two_rule_calls_started_together_write_one_rejected_row_per_session(self):
        calls = [subprocess.Popen(["python3", "-I", str(toolkit_paths.REVIEW_DIR / "phase_asks.py"), "rule",
                                   "rejected:a", "accepted:b"], cwd=self.repo, env=self.environment(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _call in range(2)]
        results = [call.communicate(timeout=60) for call in calls]

        self.assertEqual([call.returncode for call in calls], [0, 0], results)
        self.assertEqual(len(self.rejected_rows(SESSION)), 1)


class RepoKeyTest(RejectionCase):
    def test_a_linked_worktree_is_keyed_the_way_the_loop_reads_it(self):
        worktree = self.temp_root / "linked"
        subprocess.run(["git", "worktree", "add", "-q", "-b", "side", str(worktree)], cwd=self.repo,
                       env={**os.environ, **GIT_ENV}, check=True, capture_output=True)
        worktree_top = str(worktree.resolve())
        handback_store.record_phase_asks_open(SESSION, worktree_top, [dict(item) for item in ASKS], CONTEXT, "loop-w:1")

        done = subprocess.run(["python3", "-I", str(toolkit_paths.REVIEW_DIR / "phase_asks.py"), "rule",
                               "rejected:a", "accepted:b"], cwd=worktree, text=True, capture_output=True,
                              env=self.environment())

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(handback_store.rejected_ask_texts(SESSION, worktree_top), [FIRST_TEXT])
        self.assertEqual(self.rejected_in(SESSION), [])
        self.assertTrue(self.raised_again_is_dropped(SESSION, REVIEWER_WORDING, repo=worktree))


class FailureWritesNothingTest(RejectionCase):
    def test_a_damaged_row_exits_one_and_writes_no_rejected_row(self):
        store_file = handback_store.session_file(SESSION)
        damaged = {**self.store_rows(handback_store.PHASE_ASKS_OPEN)[0], "asks": "not a list"}
        store_file.write_text(store_file.read_text() + json.dumps(damaged) + "\n")

        code, _, errors = self.run_script("rule", "rejected:a", "rejected:b")

        self.assertEqual(code, 1)
        self.assertIn(str(store_file), errors)
        self.assertEqual(self.rejected_rows(SESSION), [])

    @unittest.skipIf(os.geteuid() == 0, "root writes to a read-only folder")
    def test_an_unwritable_store_exits_one_before_any_row_or_log(self):
        store_file = handback_store.session_file(SESSION)
        os.chmod(store_file, 0o444)
        os.chmod(store_file.parent, 0o555)
        self.addCleanup(os.chmod, store_file.parent, 0o755)

        code, _, errors = self.run_script("rule", "rejected:a", "rejected:b")

        self.assertEqual(code, 1)
        self.assertIn(str(store_file), errors)
        self.assertEqual(self.rejected_rows(SESSION), [])
        self.assertEqual(self.outcome_rows(), [])
