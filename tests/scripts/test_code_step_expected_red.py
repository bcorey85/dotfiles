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

    def test_a_coder_hand_back_that_edits_a_later_phase_file_is_denied(self):
        self.begin_coder()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")

        result = self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 1 — x\nREVIEW: recommended")

        self.assertIn('"permissionDecision": "deny"', result.stdout)
        self.assertIn("files the plan gives to a later phase: backend/src/totals.ts", result.stdout)

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
        self.assertNotIn("guidance", self.state())

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
