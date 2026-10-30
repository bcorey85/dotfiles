"""What /code hands back when a run stops on an agent's report or silence: question.md names why, each open item and
the command that goes on; a late review-loop hand-back routes on its report; the plan-edit coder's open choice reaches
the user.

run: python3 -m unittest test_code_step_hand_back
"""
import time

import test_code_step as base

SETUP_FAULT_PACKET = "status: setup-fault\niter: 1\nblockers:\n  - finding: no package.json\n    file_line: none"
BLOCKER_PACKET = "status: critical-blocker\niter: 1\nblockers:\n  - finding: b\n    file_line: backend/src/orders.ts:1"
UNVERIFIED_PACKET = ("status: converged\niter: 1\nfixed: []\nask: []\nnit: []\n"
                     "full_check: unverified (exit 0, no runner summary)\nfull_check_command: npm run lint")
CHECK_ONLY_PACKET = ("status: converged\niter: 1\nfixed: []\nask: []\nnit: []\n"
                     "full_check: passed (check only; CI runs the full suite)\nfull_check_command: cargo check")
CONVERGED_PACKET_HEAD = "status: converged\niter: 1\nfixed: []\nask: []\nnit: []\n"
QUALITY_CHECK_FIX = "add a Quality check: `<the command that runs the tests>` line to the repo's CLAUDE.md"
# The full-check results of a check that did not run, so the review verified nothing.
CHECK_NOT_RUN_RESULTS = (
    ("not run (timeout)", "make the check finish under the time limit"),
    ("not run (scoped command: it names files or tests, so it is no full check)", QUALITY_CHECK_FIX),
    ("not run (unresolved command: what it runs cannot be read, so it is no full check)", QUALITY_CHECK_FIX),
)
# A converged and a deferred review stop and finish alike on the full check.
REVIEW_PACKET_HEADS = {
    "converged": CONVERGED_PACKET_HEAD,
    # An empty findings_remaining is an unreadable deferred packet: one open finding makes it readable.
    "deferred": "status: deferred\niter: 1\nfixed: []\nfindings_remaining:\n- {finding: x, file_line: a.ts:1}\n"
                "ask: []\nnit: []\n",
}
# The not-run results that leave the phase to finish: CI runs the suite, the repo names no check, the plan expects
# the check red until a later phase, or the check hit a check-command error or an environment gap.
CHECK_NOT_OWED_RESULTS = (
    "not run (CI)",
    "not run (no check found; the coder's scoped tests stand)",
    "not run (expected red until Phase 2)",
    "not run (check-command error: sh: 1: cd: can't cd to gone)",
    "not run (environment gap: No module named 'requests')",
)
CACHE_ASK = ('{"finding": "f", "file_line": "backend/src/orders.ts:2", "question": "keep the cache?", '
             '"change": "drop the cache", "gate": "code-reviewer", "class": "correctness"}')
# A converged packet with no fixed or ask line: the questions test appends its own.
NO_ASK_HEAD = "status: converged\niter: 1\nnit: []\n"
CAP_PACKET = "status: cap-reached\niter: 2\nfindings_remaining:\n  - finding: x\n    file_line: a.ts:1"


class HandBackTest(base.CodeStepTest):
    def setUp(self):
        # The fixture class holds the other files' tests: only this class's own run here.
        if self._testMethodName not in vars(type(self)):
            self.skipTest("inherited test")
        super().setUp()

    def question(self):
        question_path = self.repo / ".git/code-step/question.md"
        return question_path.read_text() if question_path.exists() else ""

    def assert_stop_question(self, why, *items):
        question_text = self.question()
        self.assertIn("## The run stopped", question_text)
        self.assertIn(f"Why: {why}", question_text)
        for item in items:
            self.assertIn(f"- {item}", question_text)
        self.assertIn("Next: ", question_text)
        return question_text

    def test_a_coder_stop_on_its_report_writes_question_md_with_the_report_and_the_restart(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none\nblocked on two steps")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("the coder produced no reviewable change", "blocked on two steps")
        self.assertIn(f"`{self.own_command('resume')}`", question_text)
        self.assertIn("start --restart", question_text)

    def stop_after_review(self, packet):
        self.coder_round()
        self.hook("review-loop", packet)
        return self.step("resume")

    def stop_on_the_coder_wait_cap(self):
        self.start_phase_one()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")
        return self.step("resume")

    def stop_on_a_failed_closing_check(self, *findings):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)
        finding_options = [option for finding in findings for option in ("--finding", finding)]
        return self.step("skill-done", "fail", *finding_options)

    def test_a_stop_writes_question_md_with_why_each_open_item_and_the_command_that_goes_on(self):
        stops = [
            ("critical blocker", lambda: self.stop_after_review(BLOCKER_PACKET),
             "the review found a critical blocker", ["b - backend/src/orders.ts:1"],
             ["start --restart", "review-again"], []),
            ("setup fault", lambda: self.stop_after_review(SETUP_FAULT_PACKET),
             "the review's full check could not run here", ["no package.json"], ["review-again"],
             ["toolkit or environment fault, not a code failure"]),
            ("review cap", lambda: self.stop_after_review(CAP_PACKET),
             "the review cap was reached with findings still open", [], ["a.ts:1"], []),
            ("coder wait cap", self.stop_on_the_coder_wait_cap, "The coder has not handed back in", [],
             ["start --restart"], []),
            ("closing check with findings",
             lambda: self.stop_on_a_failed_closing_check("stale mutant count", "no follow-up line"),
             "the closing phase's check failed", ["stale mutant count", "no follow-up line"], [], []),
            ("closing check with no finding", self.stop_on_a_failed_closing_check,
             "the closing phase's check failed", [], [], []),
        ]
        for label, stop, why, items, question_texts, out_texts in stops:
            with self.subTest(label):
                self.setUp()
                out = stop()

                self.assertIn("ACTION: stop", out)
                self.assertEqual("stopped", self.state()["stage"])
                question_text = self.assert_stop_question(why, *items)
                for expected in question_texts:
                    self.assertIn(expected, question_text)
                for expected in out_texts:
                    self.assertEqual(1, out.count(expected))

    def test_a_converged_review_whose_full_check_ran_no_tests_stops_the_phase_and_asks_for_a_quality_check_line(self):
        self.coder_round()
        self.hook("review-loop", UNVERIFIED_PACKET)

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertEqual(("stopped", "check-unverified"), (self.state()["stage"], self.state()["stop"]["kind"]))
        self.assertEqual(1, out.count("Do not mark the phase done."))
        why = ("the full check exited 0 and printed no test-runner summary or ran no test, so the check did not "
               "show that any test ran.")
        question_text = self.assert_stop_question(why, "npm run lint")
        self.assertIn("Quality check: `", question_text)
        self.assertIn(self.own_command("review-again"), question_text)

    def test_an_unverified_stop_in_a_repo_with_a_quality_check_line_asks_for_a_runner_summary_not_a_quality_check_line(
            self):
        (self.repo / "CLAUDE.md").write_text("- Quality check: `npm test`\n")
        self.coder_round()
        self.hook("review-loop", UNVERIFIED_PACKET)

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        question_text = self.question()
        self.assertIn("SUMMARY_LINES", question_text)
        self.assertIn("lib/test_run_output.py", question_text)
        self.assertIn("`npm test`", question_text)
        self.assertIn(self.own_command("review-again"), question_text)
        self.assertNotIn("add a Quality check", question_text)
        self.assertNotIn("add a Quality check", out)

    def test_an_unverified_stop_for_an_unrecognized_check_names_the_full_suite_ci_line_and_summary_lines(
            self):
        (self.repo / "CLAUDE.md").write_text("- Quality check: `cargo fmt --check && cargo check`\n")
        self.coder_round()
        self.hook("review-loop", UNVERIFIED_PACKET)

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertEqual("check-unverified", self.state()["stop"]["kind"])
        question_text = self.question()
        self.assertIn("Full suite: CI", question_text)
        self.assertIn("`cargo fmt --check && cargo check`", question_text)
        self.assertIn("SUMMARY_LINES", question_text)
        self.assertIn(self.own_command("review-again"), question_text)

    def test_a_converged_review_whose_check_ran_with_no_tests_in_a_ci_repo_finishes_the_phase(self):
        (self.repo / "CLAUDE.md").write_text("- Full suite: CI\n- Quality check: `cargo check`\n")
        self.coder_round()
        self.hook("review-loop", CHECK_ONLY_PACKET)

        out = self.step("resume")

        self.assertIn("Phase 1 marked done", out)
        self.assertNotEqual("stopped", self.state().get("stage"))

    def test_a_not_run_stop_in_a_repo_with_a_quality_check_line_names_the_configured_check_not_a_new_line(self):
        for result in (CHECK_NOT_RUN_RESULTS[1][0], CHECK_NOT_RUN_RESULTS[2][0]):
            with self.subTest(result):
                self.setUp()
                (self.repo / "CLAUDE.md").write_text("- Quality check: `npm test`\n")
                self.coder_round()
                self.hook("review-loop",
                          CONVERGED_PACKET_HEAD + f"full_check: {result}\nfull_check_command: npm t a.test.ts")

                out = self.step("resume")

                self.assertIn("ACTION: stop", out)
                question_text = self.question()
                self.assertIn("the configured check (`npm test`) as written", question_text)
                self.assertNotIn("Quality check:", question_text)
                self.assertNotIn("Quality check:", out)

    def test_a_converged_or_deferred_review_whose_full_check_did_not_run_stops_the_phase_naming_the_result(self):
        for status, packet_head in REVIEW_PACKET_HEADS.items():
            for result, fix_text in CHECK_NOT_RUN_RESULTS:
                with self.subTest(f"{status}: {result}"):
                    self.setUp()
                    self.coder_round()
                    self.hook("review-loop", packet_head + f"full_check: {result}\nfull_check_command: npm test")

                    out = self.step("resume")

                    self.assertIn("ACTION: stop", out)
                    self.assertEqual(("stopped", "check-not-run"),
                                     (self.state()["stage"], self.state()["stop"]["kind"]))
                    self.assertEqual(1, out.count("Do not mark the phase done."))
                    question_text = self.question()
                    self.assertIn(result, question_text)
                    self.assertIn("`npm test`", question_text)
                    self.assertIn(fix_text, question_text)
                    self.assertIn(self.own_command("review-again"), question_text)

    def test_a_converged_or_deferred_review_whose_full_check_was_not_owed_finishes_the_phase(self):
        for status, packet_head in REVIEW_PACKET_HEADS.items():
            for result in CHECK_NOT_OWED_RESULTS:
                with self.subTest(f"{status}: {result}"):
                    self.setUp()
                    self.coder_round()
                    self.hook("review-loop", packet_head + f"full_check: {result}")

                    out = self.step("resume")

                    self.assertIn("Phase 1 marked done", out)
                    self.assertNotEqual("stopped", self.state().get("stage"))

    def test_a_stop_lists_the_reviewers_questions_apart_from_the_open_items_and_names_review_again(self):
        stops = [
            ("critical blocker", {"blockerCarried": True}, BLOCKER_PACKET,
             "`" + self.own_command("review-again") + "`"),
            ("review cap", {"capCarried": True}, CAP_PACKET, "start --restart"),
            ("check not run", {}, NO_ASK_HEAD + "full_check: not run (timeout)\nfull_check_command: npm test",
             "review-again"),
            ("check unverified", {}, NO_ASK_HEAD + "full_check: unverified (exit 0, no runner summary)\n"
                                                   "full_check_command: npm run lint", "review-again"),
        ]
        for label, carried, packet, next_command in stops:
            with self.subTest(label):
                self.setUp()
                self.coder_round()
                self.set_state(**carried)
                self.hook("review-loop", packet + f"\nfixed: []\nask: [{CACHE_ASK}]")

                out = self.step("resume")

                question_text = self.question()
                self.assertIn("Open questions:", question_text, out)
                open_items, _, open_questions = question_text.partition("Open questions:")
                self.assertIn("keep the cache?", open_questions)
                self.assertNotIn("keep the cache?", open_items)
                self.assertIn("Open questions:", out)
                self.assertIn("keep the cache?", out)
                self.assertIn(next_command, question_text)

    def test_the_review_wait_cap_stop_writes_question_md_with_the_resume_command(self):
        out = self.stop_the_review_at_the_wait_cap()

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("The review-loop has not handed back in")
        self.assertIn("review-again", question_text)

    def test_a_review_loop_messaged_before_the_wait_cap_that_hands_back_after_it_is_recorded_on_resume(self):
        # The incident shape: the fork's SendMessage was queued before the stop, and none came after it.
        self.stop_the_review_at_the_wait_cap(queued_message=True)
        self.hook("review-loop", self.LOOP_OK, agent_id="r1")

        out = self.step("resume")

        self.assertNotIn("ACTION: ask-user", out)
        self.assertNotIn("never handed back", self.question())
        self.assertNotIn("has not handed back in", self.question())
        self.assertIn("marked done", out)
        self.assertNotEqual("stopped", self.state()["stage"])
        self.assertNotIn("stop", self.state())

    def test_the_plan_edit_coders_open_choice_reaches_the_hand_back_and_the_prompt_says_where_it_goes(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it, drop the header")
        self.assertIn("OPEN CHOICE:", out)
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.hook("coder", "BEHAVIOR: plan rewritten\nOPEN CHOICE: add one more later step?", agent_id="p1")

        out = self.step("resume")

        self.assertIn("AGENT: review-loop", out)
        self.assertIn("- add one more later step?", self.said())

    def test_a_second_review_dispatch_replaces_the_first_implemented_block_in_say_md(self):
        # No stop hook ran after the earlier dispatch, so say.md still holds its block.
        report = "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"
        self.begin_coder()
        say_path = self.repo / ".git/code-step/say.md"
        say_path.write_text(
            "Note: gate skipped\n\nImplemented: the first try\nFlagged: none.\n"
            "  backend/src/orders.ts:3-5 - order matters\n"
            "Auto-dispatching review to check the implementation before committing.\n\n"
        )
        self.hook("coder", report)

        self.step("resume")

        said = say_path.read_text()
        self.assertNotIn("the first try", said)
        self.assertIn("Note: gate skipped", said)
        self.assertEqual(1, said.count("Implemented: "), said)
        self.assertEqual(1, said.count("Flagged: "), said)
        self.assertEqual(1, said.count("backend/src/orders.ts:3-5 - order matters"), said)
