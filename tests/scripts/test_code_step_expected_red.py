"""What /code does with a plan's Expected red lines and later-phase files, and with the main session's guidance: the
plan check refuses a wrong Expected red line, a coder may not hand back an edit to a file only a later phase names, the
review dispatch carries the later-phase files, and `guide` records guidance that every later dispatch of the run
carries.

run: python3 -m unittest test_code_step_expected_red
"""
import test_code_step as base

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


if __name__ == "__main__":
    base.unittest.main()
