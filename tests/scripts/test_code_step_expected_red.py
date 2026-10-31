"""What /code does with a plan's Expected red lines and later-phase files, and with the main session's guidance: the
plan check refuses a wrong Expected red line, a coder's hand-back of an edit to a file only a later phase names is
denied once per file per agent and the repeat goes through and is flagged, the review dispatch carries the
later-phase files, `guide` records guidance that every later dispatch of the phase carries, and the run notes given
at start reach every coder.

run: python3 -m unittest test_code_step_expected_red
"""
import time

import test_code_step as base

import code_step_hooks  # isort: skip  (on sys.path once test_code_step is imported)

QUALITY_CHECK = "npm run lint && npx vitest run"
EXPECTED_RED = "Expected red: `npx vitest run` until Phase 2"


class ExpectedRedTest(base.CodeStepTest):
    def setUp(self):
        # The fixture class holds the other files' tests: only this class's own run here.
        if self._testMethodName not in vars(type(self)):
            self.skipTest("inherited test")
        super().setUp()
        (self.repo / "CLAUDE.md").write_text(f"Quality check: `{QUALITY_CHECK}`\n")

    def plan_with_line(self, line):
        return self.plan_text().replace("#### Manual Verification:", f"{line}\n\n#### Manual Verification:", 1)

    def plan_check(self, text):
        plan_path = self.repo / "check.md"
        plan_path.write_text(text)
        return base.run(self.repo, self.env, "plan", "check", str(plan_path))

    def test_plan_check_passes_an_expected_red_step_until_a_later_phase(self):
        result = self.plan_check(self.plan_with_line(EXPECTED_RED))
        self.assertEqual((0, ""), (result.returncode, result.stdout))

    def test_plan_check_from_a_subdirectory_reads_the_repo_quality_check(self):
        plan_path = self.repo / "check.md"
        plan_path.write_text(self.plan_with_line(EXPECTED_RED))
        result = base.run(self.repo / "backend", self.env, "plan", "check", str(plan_path))
        self.assertEqual((0, ""), (result.returncode, result.stdout))

    def test_plan_check_from_a_subdirectory_finds_a_repo_root_script_in_a_verification_item(self):
        script = self.repo / "check"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o755)
        text = self.plan_with_line(EXPECTED_RED).replace("`npx vitest run`", "`./check`", 1)
        plan_path = self.repo / "check.md"
        plan_path.write_text(text)
        result = base.run(self.repo / "backend", self.env, "plan", "check", str(plan_path))
        self.assertEqual((0, ""), (result.returncode, result.stdout))

    def test_plan_check_refuses_an_expected_red_line_that_does_not_hold(self):
        cases = [
            ("an unknown phase", EXPECTED_RED.replace("Phase 2", "Phase 9"), "expected-red-unknown-phase"),
            ("an earlier phase", EXPECTED_RED.replace("Phase 2", "Phase 1"), "expected-red-not-later"),
            ("another form", "Expected red: npx vitest run until Phase 2", "expected-red-form"),
            ("no step of the check", EXPECTED_RED.replace("npx vitest run", "npx jest"),
             "expected-red-not-the-check"),
        ]
        for message, line, kind in cases:
            with self.subTest(message):
                result = self.plan_check(self.plan_with_line(line))
                self.assertEqual(1, result.returncode)
                self.assertIn(f": {kind}: ", result.stdout)

    LATER_PHASE_REPORT = "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 1 — x\nREVIEW: recommended"

    def reach_asks_coder(self):
        # A coder round, then a review that asks, answered as accepted: the next coder is the ask-fix coder.
        self.begin_coder()
        self.hook("coder", self.LATER_PHASE_REPORT)
        self.step("resume")
        self.hook("review-loop", self.ASK)
        self.step("resume")
        self.step("asks-done", "accepted")

    def assert_later_phase_edit_denied(self):
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")

        result = self.hook("coder", self.LATER_PHASE_REPORT)

        self.assertIn('"permissionDecision": "deny"', result.stdout)
        self.assertIn("files the plan gives to a later phase: backend/src/totals.ts", result.stdout)

    def test_a_coder_hand_back_that_edits_a_later_phase_file_is_denied(self):
        self.begin_coder()
        self.assert_later_phase_edit_denied()

    def test_a_coder_hand_back_off_the_start_commit_is_not_denied_and_stops_on_the_old_start_commit(self):
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.commit_all()
        self.begin_coder()
        base_head = self.state()["baseHead"]
        self.git("reset", "-q", "--hard", "HEAD~1")

        result = self.hook("coder", self.LATER_PHASE_REPORT)

        self.assertNotIn("permissionDecision", result.stdout)
        out = self.step("resume")
        self.assertIn("ACTION: stop", out)
        self.assertIn(base_head, out)

    def test_an_asks_coder_hand_back_that_edits_a_later_phase_file_is_denied(self):
        self.reach_asks_coder()
        self.assert_later_phase_edit_denied()

    def test_a_hand_back_from_a_non_coder_that_edits_a_later_phase_file_is_not_denied(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")

        result = self.hook("review-loop", self.LOOP_OK)

        self.assertNotIn("permissionDecision", result.stdout)

    def test_a_coder_hand_back_whose_later_phase_check_cannot_read_the_plan_goes_through_with_a_note(self):
        self.begin_coder()
        (self.repo / self.plan).write_bytes(b"\xff\xfe\x00")

        result = self.hook("coder", self.LATER_PHASE_REPORT)

        self.assertNotIn("permissionDecision", result.stdout)
        self.assertIn(f"later-phase check of plan {self.plan} failed", result.stderr)

    def test_a_file_the_phase_names_too_stays_editable(self):
        shared = self.plan_text().replace("**File**: `backend/src/orders.test.ts`",
                                          "**File**: `backend/src/orders.test.ts`\n**File**: `backend/src/totals.ts`")
        (self.repo / self.plan).write_text(shared)
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")

        result = self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 1 — x\nREVIEW: recommended")

        self.assertNotIn("later phase", result.stdout)

    def test_the_review_dispatch_names_the_later_phase_files(self):
        out = self.coder_round()

        self.assertIn("later-phase files: backend/src/audit.ts, backend/src/totals.ts", out)

    def test_the_denial_tells_the_coder_to_undo_only_its_own_edits_and_logs_the_file(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")

        result = self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        self.assertIn("never revert a file you did not edit", result.stdout)
        self.assertIn("A problem with this gate is `cause: toolkit`, never `cause: plan`", result.stdout)
        denials = self.events_named("later-phase-deny")
        self.assertEqual([("c1", ["backend/src/totals.ts"])], [(e["agent_id"], e["files"]) for e in denials])

    def test_a_second_hand_back_with_the_same_file_goes_through_and_the_review_flags_the_file(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        result = self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        self.assertNotIn("permissionDecision", result.stdout)
        self.assertEqual(1, len(self.events_named("later-phase-pass")))
        out = self.step("resume")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("changed outside the coder's scope, left in place at hand-back: backend/src/totals.ts", out)

    def test_a_hand_back_with_a_new_later_phase_file_is_denied_again_naming_only_the_new_file(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")
        (self.repo / "backend/src/audit.ts").write_text("export const a = 1\n")

        result = self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        self.assertIn("files the plan gives to a later phase: backend/src/audit.ts.", result.stdout)
        self.assertEqual([["backend/src/totals.ts"], ["backend/src/audit.ts"]],
                         [e["files"] for e in self.events_named("later-phase-deny")])

    def test_a_denial_of_one_coder_does_not_let_another_coder_through(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        result = self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c2")

        self.assertIn('"permissionDecision": "deny"', result.stdout)

    def test_a_wait_cap_stop_on_a_coder_whose_hand_back_was_denied_names_the_file(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn("files the plan gives to a later phase: backend/src/totals.ts", out)
        self.assertIn("denied an earlier attempt: Do not hand back yet.", out)

    def test_resuming_a_stopped_coder_with_no_saved_report_names_the_denied_hand_back(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")
        self.step("resume")

        self.step("resume")

        self.assertIn("(no report saved; the hand-back gate denied an earlier attempt) Do not hand back yet.",
                      self.said())

    PLAN_IMPACT_BLOCK = ("PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\n  acceptance_criteria: none\n"
                         "  cause: plan")

    def test_a_denied_attempt_with_a_block_then_a_retry_without_it_asks_the_user(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        denied = self.hook("coder", self.PLAN_IMPACT_BLOCK + "\nPLAN-IMPACT: yes", agent_id="c1")
        self.assertIn('"permissionDecision": "deny"', denied.stdout)
        self.hook("coder", self.LATER_PHASE_REPORT, agent_id="c1")

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("no longer carries this block", self.said())

    def test_impact_replaced_is_true_for_a_newest_message_with_another_block_and_false_for_the_same_block(self):
        other_block = self.PLAN_IMPACT_BLOCK.replace("assumed: A", "assumed: Z")
        cases = {
            "another block": (other_block, True),
            "the same block": (self.PLAN_IMPACT_BLOCK, False),
        }
        for name, (newest_message, expected) in cases.items():
            with self.subTest(name):
                report = {"attempts": [], "messages": [self.PLAN_IMPACT_BLOCK, newest_message]}
                self.assertIs(expected, base.code_step_report.impact_replaced([report], self.PLAN_IMPACT_BLOCK))

    def test_impact_replaced_is_false_when_no_hand_back_went_through_or_no_attempt_carries_the_block(self):
        cases = {
            "a denied attempt and no hand-back": {"attempts": [self.PLAN_IMPACT_BLOCK], "messages": []},
            "a hand-back with no block": {"attempts": [], "messages": ["BEHAVIOR: x"]},
        }
        for name, report in cases.items():
            with self.subTest(name):
                self.assertIs(False, base.code_step_report.impact_replaced([report], self.PLAN_IMPACT_BLOCK))

    def test_guide_with_no_open_run_records_nothing(self):
        out = self.step("guide", "use the money helper")

        self.assertIn("ACTION: go-on", out)
        self.assertIn("no /code run is open here", out)

    def test_guide_with_no_text_records_nothing(self):
        self.start_phase_one()

        out = self.step("guide", "  ")

        self.assertIn("ACTION: go-on", out)
        state = self.state()
        self.assertIn("stage", state)
        self.assertNotIn("guidance", state)

    def guided_asks_round(self, *guidance):
        # A coder round after the main session's guide calls, then one accepted ask. Returns the review's dispatch and
        # the ask-fix coder's dispatch.
        self.begin_coder()
        for text in guidance:
            self.step("guide", text)
        self.hook("coder", self.LATER_PHASE_REPORT)
        review_out = self.step("resume")
        self.hook("review-loop", self.ASK)
        self.step("resume")
        coder_out = self.step("asks-done", "accepted")
        return review_out, coder_out

    def test_run_notes_after_the_plan_reach_the_first_coder_once_and_the_ask_fix_coder(self):
        run_notes = "report to the orchestrator pane; run only the orders tests"
        first_coder_out = self.start_phase_one("--phase", "1", run_notes)
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.LATER_PHASE_REPORT)
        self.step("resume")
        self.hook("review-loop", self.ASK)
        self.step("resume")

        ask_fix_coder_out = self.step("asks-done", "accepted")

        self.assertEqual(1, first_coder_out.count(run_notes))
        self.assertIn(run_notes, ask_fix_coder_out)

    def test_two_guides_share_one_review_header_line_and_one_coder_bullet_each(self):
        review_out, coder_out = self.guided_asks_round("use the money helper", "keep ints")

        self.assertIn("guidance: use the money helper | keep ints", review_out)
        bullets = [line for line in coder_out.splitlines() if line.startswith("- ")]
        self.assertEqual(["- use the money helper", "- keep ints"], bullets)

    def test_a_multi_line_guide_still_makes_one_review_header_line(self):
        review_out, _coder_out = self.guided_asks_round("keep ints\nand floats")

        header_lines = [line for line in review_out.splitlines() if line.startswith("guidance:")]
        self.assertEqual(["guidance: keep ints and floats"], header_lines)

    def test_guidance_survives_a_resume_and_reaches_the_review_and_the_next_coder(self):
        self.begin_coder()
        out = self.step("guide", "use the money helper for totals")
        self.assertIn("ACTION: go-on", out)
        stage = self.state()["stage"]

        self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — x\nREVIEW: recommended")
        review_out = self.step("resume")
        self.assertIn("guidance: use the money helper for totals", review_out)
        self.assertEqual("coder", stage)

        self.hook("review-loop", self.ASK)
        self.step("resume")
        coder_out = self.step("asks-done", "accepted")
        self.assertIn("## Guidance from the main session", coder_out)
        self.assertIn("- use the money helper for totals", coder_out)
        self.assertEqual(self.plan_text(), (self.repo / self.plan).read_text())


class NewestLaterPhaseDenyReasonTest(base.unittest.TestCase):
    def test_the_newest_denial_of_the_agent_wins_and_an_agent_never_denied_has_none(self):
        events = [
            {"event": "later-phase-deny", "agent_id": "c1", "reason": "old"},
            {"event": "later-phase-deny", "agent_id": "c2", "reason": "other"},
            {"event": "later-phase-deny", "agent_id": "c1", "reason": "new"},
        ]

        self.assertEqual("new", base.code_step_core.newest_later_phase_deny_reason(events, "c1"))
        self.assertIsNone(base.code_step_core.newest_later_phase_deny_reason(events, "c3"))


class OutsideScopeFlagsTest(base.unittest.TestCase):
    def passed(self, ts, agent_id, files):
        return {"event": "later-phase-pass", "ts": ts, "agent_id": agent_id, "files": files}

    def test_only_passes_after_the_newest_dispatch_count_one_line_per_agent_with_sorted_merged_files(self):
        dispatch = {"event": "dispatch", "ts": 2, "id": "d1"}
        cases = {
            "pass before the dispatch": ([self.passed(1, "c1", ["a.ts"]), dispatch], []),
            "pass after the dispatch": ([dispatch, self.passed(3, "c1", ["a.ts"])], ["a.ts"]),
            "two agents": ([dispatch, self.passed(3, "c1", ["a.ts"]), self.passed(4, "c2", ["b.ts"])],
                           ["a.ts", "b.ts"]),
            "one agent twice": ([dispatch, self.passed(3, "c1", ["b.ts"]), self.passed(4, "c1", ["a.ts", "b.ts"])],
                                ["a.ts, b.ts"]),
        }
        for name, (events, expected_files) in cases.items():
            with self.subTest(name):
                flags = code_step_hooks.outside_scope_flags(events)
                self.assertEqual(len(expected_files), len(flags))
                for flag, files in zip(flags, expected_files, strict=True):
                    self.assertIn(f"left in place at hand-back: {files}.", flag)


if __name__ == "__main__":
    base.unittest.main()
