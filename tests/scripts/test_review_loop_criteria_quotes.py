"""Tests for review_loop_criteria_quotes.py: a fix pass never removes criterion-quoted text from a reviewed file."""
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import finding_record
import review_asks
import review_loop_criteria_quotes
import review_loop_findings
import review_loop_put_back
import review_loop_ruled
import review_loop_signoffs
import script_utils
import test_review_loop_script as loop_tests

QUOTED = "set the Bash timeout up to 600000 ms"
INCIDENT_BEFORE = f"a = 1\n# {QUOTED}\nb = 2\n"
INCIDENT_AFTER = "a = 10\n# about 150 seconds\nb = 2\n"
LIMIT_REWRITE = "limit = 1\nlimit = 20\nlimit = three\nlimit = 4\nlimit = 6\n"
LIMIT_PUT_BACK = "limit = 1\nlimit = 20\nlimit = 3\nlimit = 4\nlimit = 6\n"


class FakeQuoteRun(review_loop_criteria_quotes.AcQuoteRuns):
    """A LoopRun stand-in with what `undo_ac_quote_pass` reads: a repo and the asks it files."""

    def __init__(self, repo):
        self.repo = str(repo)
        self.asks = []
        self.rejected_questions = []
        self.dropped_asks = []

    drop_asks = review_loop_ruled.RuledFindings.drop_asks
    file_put_back_ask = review_loop_ruled.RuledFindings.file_put_back_ask

    def add_ask(self, gate, finding):
        self.asks.append(finding)


class CriteriaQuoteUnitTest(unittest.TestCase):
    """`undo_ac_quote_pass` on plain files, with no loop around it."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.repo = pathlib.Path(self.dir.name)
        self.run_ = FakeQuoteRun(self.repo)

    def pass_over(self, before, after, span=QUOTED, findings=(), skip=(), run=None):
        """Write `before`, snapshot it with `span` quoted by one criterion, write `after`, run the put-back.

        `after` of None deletes the file. Returns the put-back.
        """
        target = self.repo / "app.py"
        target.write_text(before)
        snapshot = review_loop_criteria_quotes.AcQuoteSnapshot({"app.py": before}, {"app.py": {span: ["AC1"]}})
        if after is None:
            target.unlink()
        else:
            target.write_text(after)
        return (run or self.run_).undo_ac_quote_pass(snapshot, list(findings), skip)

    def app_text(self):
        return (self.repo / "app.py").read_text()

    def test_a_rewritten_line_that_dropped_an_ac_quote_is_put_back_and_files_one_ask_naming_the_ac(self):
        put_back = self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER)

        self.assertEqual(self.app_text(), "a = 10\n" + f"# {QUOTED}\nb = 2\n")
        self.assertEqual([entry.path for entry in put_back], ["app.py"])
        self.assertEqual(len(self.run_.asks), 1)
        ask = self.run_.asks[0]
        self.assertEqual((ask.path, ask.line), ("app.py", 2))
        self.assertIn("AC1", ask.text)
        self.assertIn(QUOTED, ask.text)

    def test_other_edits_in_the_same_file_stay(self):
        self.pass_over(INCIDENT_BEFORE + "c = 3\n", INCIDENT_AFTER + "c = 30\n")

        self.assertEqual(self.app_text(), f"a = 10\n# {QUOTED}\nb = 2\nc = 30\n")

    def test_an_uneven_rewrite_keeps_the_pass_s_new_lines_and_puts_the_quoted_line_back(self):
        before = "limit = 1\nlimit = 2\nlimit = 3\nlimit = 4\nlimit = 5\n"
        after = "limit = 1\nlimit = 20\nlimit = three\nextra = 9\nlimit = 4\nlimit = 5\n"

        self.pass_over(before, after, span="limit = 3")

        self.assertEqual(self.app_text(),
                         "limit = 1\nlimit = 3\nlimit = 20\nlimit = three\nextra = 9\nlimit = 4\nlimit = 5\n")
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_moved_span_is_no_removal(self):
        moved = f"# {QUOTED}\na = 1\nb = 2\n"

        put_back = self.pass_over(INCIDENT_BEFORE, moved)

        self.assertEqual((put_back, self.run_.asks, self.app_text()), ([], [], moved))

    def test_a_span_the_pass_did_not_touch_files_nothing(self):
        after = INCIDENT_BEFORE.replace("b = 2", "b = 20")

        put_back = self.pass_over(INCIDENT_BEFORE, after)

        self.assertEqual((put_back, self.run_.asks, self.app_text()), ([], [], after))

    def test_an_accepted_ask_lets_the_removal_stand(self):
        change = review_loop_criteria_quotes.remove_text_change("app.py", QUOTED)
        accepted = finding_record.parse_finding(f"app.py:2 [plan-drift] Proposed change: {change}")

        put_back = self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER, findings=[accepted])

        self.assertEqual((put_back, self.run_.asks, self.app_text()), ([], [], INCIDENT_AFTER))

    def test_an_accepted_ask_for_a_span_with_a_change_mark_and_a_newline_lets_the_removal_stand(self):
        span = "change: retry\nthree times"
        before = f"a = 1\n# {span}\nb = 2\n"
        after = "a = 10\n# about 150 seconds\nb = 2\n"
        change = review_loop_criteria_quotes.remove_text_change("app.py", span)
        accepted = finding_record.parse_finding(f"app.py:2 [plan-drift] Proposed change: {change}")
        self.assertIn("change : retry three times", change)
        self.assertIn("change : retry three times", accepted.text)

        put_back = self.pass_over(before, after, span=span, findings=[accepted])

        self.assertEqual((put_back, self.run_.asks, self.app_text()), ([], [], after))

    def test_a_rejected_ask_keeps_the_put_back_and_files_no_ask(self):
        self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER)
        rejecting = FakeQuoteRun(self.repo)
        rejecting.rejected_questions = [review_asks.ask_question(self.run_.asks[0])]

        put_back = self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER, run=rejecting)

        self.assertEqual(self.app_text(), f"a = 10\n# {QUOTED}\nb = 2\n")
        self.assertEqual(len(put_back), 1)
        self.assertEqual(rejecting.asks, [])
        self.assertEqual([reason for _ask, reason in rejecting.dropped_asks],
                         [review_loop_findings.REJECTED_ASK_REASON])

    def test_the_same_ask_is_filed_once_across_rounds(self):
        self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER)
        self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER)

        self.assertEqual(len(self.run_.asks), 1)

    def test_a_deleted_file_is_left_alone(self):
        deleted = self.pass_over(INCIDENT_BEFORE, None)

        self.assertEqual((deleted, self.run_.asks), ([], []))

    def test_a_held_file_is_left_alone(self):
        held = self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER, skip={"app.py"})

        self.assertEqual((held, self.run_.asks), ([], []))
        self.assertEqual(self.app_text(), INCIDENT_AFTER)

    def test_two_quoted_spans_lost_in_one_file_are_both_put_back_with_an_ask_each(self):
        before = "limit = 3\nkeep\nretries = 5\n"
        after = "limit = 9\nkeep\nretries = 7\n"
        target = self.repo / "app.py"
        target.write_text(before)
        spans = {"limit = 3": ["AC1"], "retries = 5": ["AC2"]}
        snapshot = review_loop_criteria_quotes.AcQuoteSnapshot({"app.py": before}, {"app.py": spans})
        target.write_text(after)

        put_back = self.run_.undo_ac_quote_pass(snapshot, [])

        self.assertEqual(self.app_text(), before)
        self.assertEqual(put_back[0].lost_numbers, [1, 3])
        self.assertEqual(len(self.run_.asks), 2)

    def test_an_ac_quote_put_back_beside_a_comment_put_back_undoes_a_finding_on_the_quoted_line(self):
        finding = finding_record.parse_finding("app.py:3 [bug] limit is wrong")
        comment_entry = review_loop_put_back.ProtectedPutBack("app.py", [1], "a\n", "a\n")
        quote_entry = review_loop_put_back.ProtectedPutBack("app.py", [3], "a\nb\nc\n", "a\nx\nc\n")
        host = types.SimpleNamespace(repo=str(self.repo))

        undid = review_loop_signoffs.SignoffRuns.put_back_undid(host, finding, [comment_entry, quote_entry])

        self.assertTrue(undid)

    def test_a_put_back_that_returned_the_file_to_its_text_undoes_a_finding_whatever_the_line(self):
        finding = finding_record.parse_finding("app.py:9 [bug] limit is wrong")
        comment_entry = review_loop_put_back.ProtectedPutBack("app.py", [1], "a\n", "a\n")
        unchanged_entry = review_loop_put_back.ProtectedPutBack("app.py", [], "a\nb\n", "a\nb\n")
        host = types.SimpleNamespace(repo=str(self.repo))

        undid = review_loop_signoffs.SignoffRuns.put_back_undid(host, finding, [comment_entry, unchanged_entry])

        self.assertTrue(undid)

    def test_a_finding_that_asks_for_the_change_still_files_an_ask(self):
        finding = finding_record.parse_finding("app.py:2 [bug] the timeout comment is wrong")

        self.pass_over(INCIDENT_BEFORE, INCIDENT_AFTER, findings=[finding])

        self.assertEqual(self.app_text(), f"a = 10\n# {QUOTED}\nb = 2\n")
        self.assertEqual(len(self.run_.asks), 1)

    def test_the_empty_snapshot_puts_nothing_back(self):
        (self.repo / "app.py").write_text(INCIDENT_AFTER)

        put_back = self.run_.undo_ac_quote_pass(review_loop_criteria_quotes.EMPTY_AC_QUOTES, [])

        self.assertEqual((put_back, self.run_.asks, self.app_text()), ([], [], INCIDENT_AFTER))


class SpanHelpersTest(unittest.TestCase):
    def test_first_lines_holding_gives_each_needle_its_first_line_and_skips_absent_ones(self):
        text = "x one\ny two\nz one two\n"

        numbers = script_utils.first_lines_holding(text, ["one", "two", "none"])

        self.assertEqual(numbers, {"one": 1, "two": 2})


class SnapshotRun(review_loop_criteria_quotes.AcQuoteRuns):
    """A LoopRun stand-in with what `ac_quote_snapshot` reads: a repo, a plan and no held files."""

    def __init__(self, repo, plan):
        self.repo = str(repo)
        self.plan = plan

    plan_path_on_disk = review_loop_ruled.RuledFindings.plan_path_on_disk

    held = frozenset()

    def coder_held_files(self):
        return set(self.held)


class AcQuoteSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.repo = pathlib.Path(self.dir.name)
        review_loop_criteria_quotes.AC_QUOTE_FAULTS.clear()
        self.addCleanup(review_loop_criteria_quotes.AC_QUOTE_FAULTS.clear)

    def write_plan(self, criteria):
        (self.repo / "plan.md").write_text("# Plan\n\n## Phase 1: Limits\n\nSet the limit.\n")
        (self.repo / "acceptance-criteria.md").write_text(criteria)

    def test_a_file_holding_a_quoted_span_is_snapshotted_with_the_criterion_label(self):
        self.write_plan('- **AC1** — the limit stays "limit = 3" in app.py\n')
        (self.repo / "app.py").write_text("limit = 3\n")
        (self.repo / "other.py").write_text("x = 1\n")

        snapshot = SnapshotRun(self.repo, "plan.md").ac_quote_snapshot(["app.py", "other.py", "gone.py"])

        self.assertEqual(snapshot.texts, {"app.py": "limit = 3\n"})
        self.assertEqual(snapshot.spans, {"app.py": {"limit = 3": ["AC1"]}})

    def test_a_file_in_the_plan_folder_and_a_held_file_are_left_out(self):
        plan = "docs/plans/limits/plan.md"
        plan_folder = self.repo / "docs" / "plans" / "limits"
        plan_folder.mkdir(parents=True)
        (plan_folder / "plan.md").write_text("# Plan\n\n## Phase 1: Limits\n\nSet the limit.\n")
        (plan_folder / "acceptance-criteria.md").write_text('- **AC1** — the limit stays "limit = 3" in app.py\n')
        (plan_folder / "notes.md").write_text("limit = 3\n")
        for name in ("app.py", "held.py"):
            (self.repo / name).write_text("limit = 3\n")
        run = SnapshotRun(self.repo, plan)
        run.held = {"held.py"}

        snapshot = run.ac_quote_snapshot(["app.py", "held.py", "docs/plans/limits/notes.md"])

        self.assertEqual(list(snapshot.texts), ["app.py"])

    def test_with_no_plan_on_disk_the_snapshot_is_empty(self):
        snapshot = SnapshotRun(self.repo, "plan.md").ac_quote_snapshot(["app.py"])

        self.assertEqual(snapshot, review_loop_criteria_quotes.EMPTY_AC_QUOTES)

    def test_a_malformed_criteria_file_gives_an_empty_snapshot_and_one_note_across_calls(self):
        criteria = '- **AC1** — the limit stays "limit = 3" in app.py\n'
        self.write_plan(criteria * 2)
        run = SnapshotRun(self.repo, "plan.md")

        first = run.ac_quote_snapshot(["app.py"])
        run.ac_quote_snapshot(["app.py"])

        self.assertEqual(first, review_loop_criteria_quotes.EMPTY_AC_QUOTES)
        self.assertEqual(len(review_loop_criteria_quotes.AC_QUOTE_FAULTS), 1)
        self.assertIn(str(self.repo / "acceptance-criteria.md"), review_loop_criteria_quotes.AC_QUOTE_FAULTS[0])

    def test_an_unreadable_criteria_file_gives_an_empty_snapshot_and_one_note(self):
        self.write_plan('- **AC1** — the limit stays "limit = 3" in app.py\n')

        with mock.patch.object(review_loop_criteria_quotes.plan_format, "plan_ac_quotes",
                               side_effect=OSError("unreadable")):
            snapshot = SnapshotRun(self.repo, "plan.md").ac_quote_snapshot(["app.py"])

        self.assertEqual(snapshot, review_loop_criteria_quotes.EMPTY_AC_QUOTES)
        self.assertEqual(len(review_loop_criteria_quotes.AC_QUOTE_FAULTS), 1)
        self.assertIn("unreadable", review_loop_criteria_quotes.AC_QUOTE_FAULTS[0])

    def test_criteria_that_quote_nothing_give_an_empty_snapshot(self):
        self.write_plan("- **AC1** — the limit stays at three\n")
        (self.repo / "app.py").write_text("limit = 3\n")

        snapshot = SnapshotRun(self.repo, "plan.md").ac_quote_snapshot(["app.py"])

        self.assertEqual(snapshot, review_loop_criteria_quotes.EMPTY_AC_QUOTES)
        self.assertEqual(review_loop_criteria_quotes.AC_QUOTE_FAULTS, [])


class CriteriaQuoteLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    """The whole script: a plan and a criteria file on disk, a coder that rewrites the quoted line."""

    PLAN = "# Plan\n\n## Phase 2: Limits\n\nSet the limit.\n"
    CRITERIA = '- **AC1** — the third limit stays "limit = 3" in app.py\n'
    USER_RULED_HEADER = "user-ruled: 1\nuser-ruled-at: 2026-11-13 11:32:00Z\n"

    def findings_header(self, *findings):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps(list(findings)))
        return f"mode: fix-first\nfindings: {findings_file}\n"

    def setUp(self):
        super().setUp()
        self.committed_app_text = (self.repo / "app.py").read_text()

    def with_plan(self, criteria=CRITERIA):
        self.commit_files({"plan.md": self.PLAN, "acceptance-criteria.md": criteria})
        (self.repo / "app.py").write_text(self.committed_app_text)

    def run_loop(self, header_extra="", reviews=None):
        scenario = {
            "code-reviewer": reviews or [{"result": loop_tests.FIX_REVIEW}, *[{"result": loop_tests.CLEAN_REVIEW}] * 3],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": LIMIT_REWRITE}}],
            "closure": [{"result": loop_tests.CLOSED}],
        }
        completed = self.run_script(scenario, header_extra=header_extra)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        return packet

    def test_loop_puts_back_the_ac_quoted_line_and_keeps_the_fix(self):
        self.with_plan()

        packet = self.run_loop()

        self.assertEqual((self.repo / "app.py").read_text(), LIMIT_PUT_BACK)
        self.assertEqual(len(packet["ask"]), 1)
        ask = str(packet["ask"][0])
        for part in ("AC1", "app.py", "limit = 3"):
            self.assertIn(part, ask)

    def test_an_accepted_ask_lets_the_loop_keep_the_removal_and_files_no_new_ask(self):
        self.with_plan()
        change = "remove the text 'limit = 3' from app.py"
        accepted = f"app.py:3 [plan-drift] Proposed change: {change}"
        header = self.findings_header(accepted) + self.USER_RULED_HEADER
        reviews = [{"result": loop_tests.CLEAN_REVIEW}] * 2

        packet = self.run_loop(header_extra=header, reviews=reviews)

        self.assertEqual((self.repo / "app.py").read_text(), LIMIT_REWRITE)
        self.assertEqual(packet["ask"], [])

    def test_a_rejected_ask_keeps_the_put_back_and_files_no_new_ask(self):
        self.with_plan()
        first_packet = self.run_loop()
        self.assertEqual(len(first_packet["ask"]), 1)
        self.reset_fake_run()
        env = {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"], "CLAUDE_CODE_SESSION_ID": loop_tests.SESSION}
        with mock.patch.dict(os.environ, env):
            review_asks.record_rejected_asks([loop_tests.SESSION], os.path.realpath(self.repo), first_packet["ask"],
                                             [review_asks.REJECTED])
        (self.repo / "app.py").write_text(self.committed_app_text)

        packet = self.run_loop()

        self.assertEqual((self.repo / "app.py").read_text(), LIMIT_PUT_BACK)
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertTrue(packet["dropped_asks"][0].startswith(review_loop_findings.REJECTED_ASK_REASON),
                        packet["dropped_asks"])

    def test_loop_with_no_plan_on_disk_leaves_ac_text_alone(self):
        self.commit_files({"acceptance-criteria.md": self.CRITERIA})
        (self.repo / "app.py").write_text(self.committed_app_text)

        packet = self.run_loop()

        self.assertEqual((self.repo / "app.py").read_text(), LIMIT_REWRITE)
        self.assertEqual(packet["ask"], [])

    def test_a_malformed_criteria_file_turns_the_guard_off_with_a_tool_fault_note_naming_the_file(self):
        self.with_plan(criteria=self.CRITERIA * 2)

        packet = self.run_loop()

        self.assertEqual((self.repo / "app.py").read_text(), LIMIT_REWRITE)
        self.assertEqual(packet["status"], "converged")
        self.assertIn(str(self.repo / "acceptance-criteria.md"), json.dumps(packet["tool_fault"]))


if __name__ == "__main__":
    unittest.main()
