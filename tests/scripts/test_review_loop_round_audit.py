"""Checks for review_loop_round_audit.py: every fix finding a round's reviewers filed reaches a coder brief or an ask
before the next review round is built, and the re-review prompt never lists an unsent finding as fixed."""
import json
import sys
import unittest

import toolkit_paths
from test_review_loop_script import APP_FIXED, CLEAN_REVIEW, CLOSED, ReviewLoopHarness

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import finding_record
import review_loop_coder
import review_loop_findings
import review_loop_round_audit
import review_loop_round_settle
import review_loop_script
from review_loop_pass_names import is_finding_pass, missed_fix_pass, round_fix_pass

SECOND_FIX = "`app.py:4` the fourth limit skips the unit"
TWO_FIX_REVIEW = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n- " + SECOND_FIX + "\n\n## Ask\nNone\n\n"
                  "## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")


def finding(text):
    return finding_record.parse_finding(text)


class AuditHost(review_loop_round_audit.RoundAudit, review_loop_round_settle.RoundSettle):
    """A LoopRun stand-in with what the audit reads: the round's fix entries, its asks and a recording repair."""

    not_put_back = review_loop_script.LoopRun.not_put_back
    keep_open = review_loop_script.LoopRun.keep_open
    drop_open = review_loop_script.LoopRun.drop_open

    def __init__(self, fixes, asks=(), changed=("app.py",), report="", reverted_findings=()):
        self.init_round_audit()
        self.iter_count = 1
        self.asks = list(asks)
        self.round_fixes = [{"finding": item, "actioned": "none"} for item in fixes]
        self.skipped_fp = []
        self.put_back_findings = []
        self.fixed = []
        self.check_fixed = 0
        self.open_fixes = []
        self.files_touched = set()
        self.repairs = []
        self.changed = list(changed)
        self.report = report
        self.reverted_findings = list(reverted_findings)

    def repair(self, call_name, findings):
        self.repairs.append((call_name, findings))
        return review_loop_coder.CoderResult(self.report, ["diff"], self.changed, ())

    def findings_on_reverted_paths(self, findings, reverted):
        return [item for item in findings if item in self.reverted_findings]

    def mark_standing_rewords_applied(self, changed):
        self.rewords_checked = list(changed)

    def record_coder_plan_impact(self, report, changed):
        self.plan_impact_reports = [report]
        return True


class RoundAuditTest(unittest.TestCase):
    def setUp(self):
        self.first = finding("`app.py:2` the limit is wrong for `limit`")
        self.second = finding(SECOND_FIX)

    def test_every_finding_in_a_brief_sends_no_extra_pass(self):
        host = AuditHost([self.first, self.second])
        host.note_briefed([self.first, self.second])

        self.assertEqual(host.send_missed_fixes().prior_entries, [])
        self.assertEqual(host.repairs, [])

    def test_a_finding_in_a_merged_brief_counts_as_briefed(self):
        host = AuditHost([self.first, self.second])
        host.note_briefed([finding_record.combine([self.first, self.second])])

        self.assertEqual(host.unsent_round_fixes(), [])

    def test_a_finding_in_no_brief_goes_to_a_coder_pass_and_reads_as_fixed_in_the_prior_issues(self):
        host = AuditHost([self.first, self.second])
        host.note_briefed([self.first])

        missed = host.send_missed_fixes()
        prior = missed.prior_entries

        self.assertEqual([(name, [item.text for item in items]) for name, items in host.repairs],
                         [("coder-missed1", [self.second.text])])
        self.assertEqual([(entry["issue"], entry["status"]) for entry in prior], [(self.second.text, "fixed")])
        self.assertEqual((missed.changed, missed.diffs, missed.applied), (["app.py"], ["diff"], [self.second]))
        self.assertEqual(host.round_fixes[1]["actioned"], "fixed")

    def test_a_finding_filed_as_an_ask_needs_no_pass(self):
        host = AuditHost([self.first, self.second], asks=[self.second])
        host.note_briefed([self.first])

        self.assertEqual(host.send_missed_fixes().prior_entries, [])

    def test_a_missed_pass_that_cannot_run_stops_the_loop_and_marks_nothing_fixed(self):
        host = AuditHost([self.first])

        def failing_repair(call_name, findings):
            raise review_loop_script.CoderFailedError("coder could not run")

        host.repair = failing_repair

        with self.assertRaises(review_loop_script.CoderFailedError):
            host.send_missed_fixes()

        self.assertEqual(host.round_fixes[0]["actioned"], "none")

    def test_an_unsent_finding_the_coder_leaves_unchanged_reads_as_skipped(self):
        host = AuditHost([self.first], changed=())

        prior = host.send_missed_fixes().prior_entries

        self.assertEqual([(entry["status"], entry["reason"]) for entry in prior],
                         [("skipped", "the coder made no change")])
        self.assertEqual(host.round_fixes[0]["actioned"], "skipped_fp")

    def test_a_skip_the_coder_reports_reads_as_skipped_though_the_pass_changed_a_file(self):
        host = AuditHost([self.first], report="SKIPPED 1: not a bug")

        missed = host.send_missed_fixes()

        self.assertEqual([(entry["status"], entry["reason"]) for entry in missed.prior_entries],
                         [("skipped", "SKIPPED 1: not a bug")])
        self.assertEqual(missed.skipped, [self.first])
        self.assertEqual(missed.applied, [])
        self.assertEqual(host.round_fixes[0]["actioned"], "skipped_fp")

    def test_a_fix_the_missed_pass_applies_counts_once_in_the_fixed_tally(self):
        host = AuditHost([self.first])

        host.send_missed_fixes()

        self.assertEqual(host.check_fixed, 0, "a finding with a run row counts through its actioned value only")
        self.assertEqual(host.fixed, [self.first])
        self.assertEqual(host.round_fixes[0]["actioned"], "fixed")
        self.assertEqual(host.rewords_checked, ["app.py"])

    def test_a_plan_impact_in_the_missed_pass_report_keeps_its_skips_open(self):
        host = AuditHost([self.first], report="PLAN-IMPACT: yes\nSKIPPED 1: needs a plan change")

        host.send_missed_fixes()

        self.assertEqual(len(host.plan_impact_reports), 1)
        self.assertEqual(host.skipped_fp, [], "a held plan impact is no false positive")
        self.assertEqual(host.open_fixes, [self.first])

    def test_an_older_skip_row_of_the_same_finding_does_not_make_a_changed_pass_read_as_skipped(self):
        host = AuditHost([self.first])
        host.skipped_fp.append({"item": self.first, "reason": "an earlier round's reason"})

        missed = host.send_missed_fixes()

        self.assertEqual([entry["status"] for entry in missed.prior_entries], ["fixed"])

    def test_a_reverted_unsent_finding_reads_as_skipped_and_is_not_actioned(self):
        host = AuditHost([self.first], reverted_findings=[self.first])

        missed = host.send_missed_fixes()

        self.assertEqual([(entry["status"], entry["reason"]) for entry in missed.prior_entries],
                         [("skipped", review_loop_findings.REVERTED_APPROVAL_EDIT_REASON)])
        self.assertEqual(host.round_fixes[0]["actioned"], "none")
        self.assertEqual(missed.applied, [])

    def test_a_put_back_unsent_finding_reads_as_partial_and_is_not_actioned(self):
        host = AuditHost([self.first])
        host.put_back_findings = [self.first]

        missed = host.send_missed_fixes()

        self.assertEqual([entry["status"] for entry in missed.prior_entries], ["partial"])
        self.assertEqual(host.round_fixes[0]["actioned"], "none")

    def test_the_pass_leaves_the_actioned_value_of_a_briefed_fix_alone(self):
        host = AuditHost([self.first, self.second])
        host.note_briefed([self.first])
        host.round_fixes[0]["actioned"] = "none"

        host.send_missed_fixes()

        self.assertEqual([entry["actioned"] for entry in host.round_fixes], ["none", "fixed"])

    def test_a_brief_of_an_earlier_round_does_not_cover_this_round(self):
        host = AuditHost([self.first])
        host.note_briefed([self.first])
        host.iter_count = 2
        host.round_fixes = [{"finding": self.first, "actioned": "none"}]

        self.assertEqual(len(host.unsent_round_fixes()), 1)


class FixRoundHost(AuditHost):
    """An AuditHost that runs the loop's own fix_round and records each fix's `actioned` mark at every coder pass."""

    fix_round = review_loop_script.LoopRun.fix_round

    def __init__(self, fixes, iter_count=review_loop_script.ROUND_BUDGET):
        super().__init__(fixes)
        self.iter_count = iter_count
        self.nits = []
        self.prior_issues = []
        self.last_fix = None
        self.files = {}
        self.marks_at_pass = {}
        self.report_of = {}
        self.changed_of = {}
        self.planned_skips = None

    late_repairs = ()

    def review_scope(self):
        return {}

    def lint_fixed_files(self, changed):
        pass

    def plan_second_round(self, round_fix, result, skipped_findings, lint_repairs=()):
        self.planned_skips = skipped_findings

    def repair(self, call_name, findings, nits=()):
        self.marks_at_pass[call_name] = [entry["actioned"] for entry in self.round_fixes]
        self.report = self.report_of.get(call_name, "")
        self.changed = self.changed_of.get(call_name, ["app.py"])
        return super().repair(call_name, findings)


class FindingPassTest(unittest.TestCase):
    def test_a_missed_pass_is_a_finding_pass_and_its_restore_pass_is_not(self):
        self.assertTrue(is_finding_pass("coder-missed2"))
        self.assertFalse(is_finding_pass("coder-missed1-restore"))


class FixRoundTest(unittest.TestCase):
    """Drives the loop's own fix_round in process. The tests of the unsent-fix marks fail before the missed pass
    existed and pass after; the no-change test fails before a no-change round pass read as skipped."""

    def setUp(self):
        self.first = finding("`app.py:2` the limit is wrong for `limit`")
        self.second = finding(SECOND_FIX)
        self.docs_first = finding("`README.md:2` [docs] the limit is misdocumented")
        self.docs_second = finding("`README.md:4` [docs] the unit is misdocumented")

    def host(self, fixes, briefed, iter_count=review_loop_script.ROUND_BUDGET):
        host = FixRoundHost(fixes, iter_count)
        host.note_briefed(briefed)
        return host

    def test_an_unsent_fix_is_not_marked_fixed_before_the_missed_pass_runs(self):
        host = self.host([self.first, self.second], [self.first])

        host.fix_round([("code-reviewer", set(), [self.first])], [])

        self.assertEqual(host.marks_at_pass[missed_fix_pass(host.iter_count)], ["fixed", "none"],
                         "the round pass marks only the fix it was briefed on")
        self.assertEqual([entry["actioned"] for entry in host.round_fixes], ["fixed", "fixed"])

    def test_the_missed_pass_results_reach_the_prior_issues_last_fix_and_touched_files(self):
        host = self.host([self.first, self.second], [self.first])
        host.changed_of = {missed_fix_pass(host.iter_count): ["lib.py"]}

        host.fix_round([("code-reviewer", set(), [self.first])], [])

        statuses = {entry["issue"]: entry["status"] for entry in host.prior_issues}
        self.assertEqual(statuses, {self.first.text: "fixed", self.second.text: "fixed"})
        self.assertEqual(host.last_fix.changed, ["app.py", "lib.py"])
        self.assertEqual(host.last_fix.diffs, ["diff", "diff"])
        self.assertIn("lib.py", host.files_touched)

    def test_a_round_pass_that_changes_nothing_reads_every_finding_as_skipped(self):
        host = self.host([self.first, self.second], [self.first, self.second])
        host.changed_of = {round_fix_pass(host.iter_count): []}

        host.fix_round([("code-reviewer", set(), [self.first, self.second])], [])

        self.assertEqual([(entry["status"], entry.get("reason")) for entry in host.prior_issues],
                         [("skipped", "the coder made no change")] * 2)

    def test_a_missed_pass_skip_reads_as_skipped_in_the_prior_issues(self):
        host = self.host([self.first, self.second], [self.first])
        host.report_of = {missed_fix_pass(host.iter_count): "SKIPPED 1: not a bug"}

        host.fix_round([("code-reviewer", set(), [self.first])], [])

        statuses = {entry["issue"]: entry["status"] for entry in host.prior_issues}
        self.assertEqual(statuses[self.second.text], "skipped")

    def test_the_second_round_plan_gets_the_findings_the_missed_pass_skipped(self):
        host = self.host([self.first, self.second], [self.first], review_loop_script.ROUND_BUDGET - 1)
        host.report_of = {missed_fix_pass(host.iter_count): "SKIPPED 1: not a bug"}

        host.fix_round([("code-reviewer", set(), [self.first])], [])

        self.assertEqual(host.planned_skips, [self.second])

    def test_a_missed_fix_outside_docs_class_forces_a_re_review_though_only_md_changed(self):
        host = self.host([self.docs_first, self.second], [self.docs_first])
        host.changed_of = {round_fix_pass(host.iter_count): ["README.md"],
                           missed_fix_pass(host.iter_count): ["NOTES.md"]}

        needs_review = host.fix_round([("code-reviewer", set(), [self.docs_first])], [])

        self.assertTrue(needs_review)

    def test_a_missed_pass_that_changes_code_forces_a_re_review_of_a_docs_fix(self):
        host = self.host([self.docs_first, self.docs_second], [self.docs_first])
        host.changed_of = {round_fix_pass(host.iter_count): ["README.md"],
                           missed_fix_pass(host.iter_count): ["app.py"]}

        needs_review = host.fix_round([("code-reviewer", set(), [self.docs_first])], [])

        self.assertTrue(needs_review)

    def test_docs_fixes_that_change_only_md_files_skip_the_re_review(self):
        host = self.host([self.docs_first, self.docs_second], [self.docs_first])
        host.changed_of = {round_fix_pass(host.iter_count): ["README.md"],
                           missed_fix_pass(host.iter_count): ["README.md"]}

        needs_review = host.fix_round([("code-reviewer", set(), [self.docs_first])], [])

        self.assertFalse(needs_review)

    def test_a_fix_held_only_by_an_ask_is_not_sent_and_reads_as_none(self):
        host = self.host([self.first, self.second], [self.first])
        host.asks = [self.second]

        host.fix_round([("code-reviewer", set(), [self.first])], [])

        self.assertEqual(host.round_fixes[1]["actioned"], "none")
        self.assertNotIn(missed_fix_pass(host.iter_count), host.marks_at_pass)


class RoundWalkTest(ReviewLoopHarness, unittest.TestCase):
    """The loop's walk through a round whose reviewer reports two fixes. Not claimed to fail before the change: it
    guards the wiring of the walk."""

    def test_both_fixes_reach_the_coder_brief_and_the_next_review_lists_both_as_fixed(self):
        completed = self.run_script({
            "code-reviewer": [{"result": TWO_FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 2.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.fake_calls()
        coder_prompts = [call["prompt"] for call in calls if call["key"] == "coder"]
        self.assertEqual(len(coder_prompts), 1)
        self.assertIn("1. `app.py:2` the limit is wrong for `limit`", coder_prompts[0])
        self.assertIn("2. `app.py:4` the fourth limit skips the unit", coder_prompts[0])
        reviews = [call["prompt"] for call in calls if call["key"] == "code-reviewer"]
        for text in ("the limit is wrong for `limit`", "the fourth limit skips the unit"):
            self.assertRegex(reviews[1], rf"issue: .*{text.replace('`', '.')}.*\n\s+status: fixed")
        self.assertEqual(json.loads((self.fake_dir / "counters.json").read_text())["coder"], 1)


if __name__ == "__main__":
    unittest.main()
