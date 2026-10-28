"""What /code hands back when a run stops on an agent's report or silence: question.md names why, each open item and
the command that goes on; a late review-loop hand-back routes on its report; the plan-edit coder's open choice reaches
the user.

run: python3 -m unittest test_code_step_hand_back
"""
import time

import test_code_step as base

SETUP_FAULT_PACKET = "status: setup-fault\niter: 1\nblockers:\n  - finding: no package.json\n    file_line: none"
BLOCKER_PACKET = "status: critical-blocker\niter: 1\nblockers:\n  - finding: b\n    file_line: backend/src/orders.ts:1"
CACHE_ASK = ('{"finding": "f", "file_line": "backend/src/orders.ts:2", "question": "keep the cache?", '
             '"change": "drop the cache", "gate": "code-reviewer", "class": "correctness"}')
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

        out = self.step("after-coder")

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("the coder produced no reviewable change", "blocked on two steps")
        self.assertIn(f"`{self.own_command('resume')}`", question_text)
        self.assertIn("start --restart", question_text)

    def test_a_critical_blocker_stop_writes_question_md_with_each_blocker(self):
        self.coder_round()
        self.hook("review-loop", BLOCKER_PACKET)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("the review found a critical blocker", "b - backend/src/orders.ts:1")
        self.assertIn("start --restart", question_text)

    def test_a_setup_fault_stop_writes_question_md_with_each_blocker_and_says_it_is_not_a_code_failure(self):
        self.coder_round()
        self.hook("review-loop", SETUP_FAULT_PACKET)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        self.assertEqual(1, out.count("toolkit or environment fault, not a code failure"))
        self.assert_stop_question("the review's full check could not run here", "no package.json")

    def test_a_critical_blocker_stop_lists_the_reviewers_questions_apart_from_the_blockers_and_names_review_again(self):
        self.coder_round()
        packet = BLOCKER_PACKET + f"\nfixed: []\nask: [{CACHE_ASK}]"
        self.hook("review-loop", packet)

        out = self.step("after-review")

        question_text = self.question()
        self.assertIn("Open questions:", question_text, out)
        open_items, _, open_questions = question_text.partition("Open questions:")
        self.assertIn("keep the cache?", open_questions)
        self.assertNotIn("keep the cache?", open_items)
        self.assertIn("Open questions:", out)
        self.assertIn("keep the cache?", out)
        self.assertIn(f"`{self.own_command('review-again')}`", question_text)

    def test_a_review_cap_stop_writes_question_md_with_each_open_finding(self):
        self.coder_round()
        self.hook("review-loop", CAP_PACKET)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("the review cap was reached with findings still open")
        self.assertIn("a.ts:1", question_text)

    def test_a_review_cap_stop_lists_the_reviewers_questions_apart_from_the_findings(self):
        self.coder_round()
        self.set_state(capCarried=True)
        self.hook("review-loop", CAP_PACKET + f"\nfixed: []\nask: [{CACHE_ASK}]")

        out = self.step("after-review")

        question_text = self.question()
        self.assertIn("Open questions:", question_text, out)
        open_items, _, open_questions = question_text.partition("Open questions:")
        self.assertIn("keep the cache?", open_questions)
        self.assertNotIn("keep the cache?", open_items)
        self.assertIn("keep the cache?", out)

    def test_the_review_wait_cap_stop_writes_question_md_with_the_resume_command(self):
        out = self.stop_the_review_at_the_wait_cap()

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("The review-loop has not handed back in")
        self.assertIn("review-again", question_text)

    def test_the_coder_wait_cap_stop_writes_question_md_with_the_restart(self):
        self.start_phase_one()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        question_text = self.assert_stop_question("The coder has not handed back in")
        self.assertIn("start --restart", question_text)

    def test_a_failed_closing_check_writes_question_md_with_each_finding(self):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)

        out = self.step("skill-done", "fail", "--finding", "stale mutant count", "--finding", "no follow-up line")

        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assert_stop_question("the closing phase's check failed", "stale mutant count", "no follow-up line")

    def test_a_failed_closing_check_with_no_finding_names_the_open_success_criteria(self):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)

        self.step("skill-done", "fail")

        self.assert_stop_question("the closing phase's check failed")

    def assert_resume_takes_the_late_hand_back(self):
        self.hook("review-loop", self.LOOP_OK, agent_id="r1")

        out = self.step("resume")

        self.assertNotIn("ACTION: ask-user", out)
        self.assertNotIn("never handed back", self.question())
        self.assertNotIn("has not handed back in", self.question())
        self.assertIn("marked done", out)
        self.assertNotEqual("stopped", self.state()["stage"])
        self.assertNotIn("resumableReview", self.state())

    def test_a_review_loop_that_hands_back_after_the_wait_cap_is_routed_on_its_report(self):
        self.stop_the_review_at_the_wait_cap()
        self.assertIn("has not handed back in", self.question())

        self.assert_resume_takes_the_late_hand_back()

    def test_a_review_loop_messaged_before_the_wait_cap_that_hands_back_after_it_is_recorded_on_resume(self):
        # The incident shape: the fork's SendMessage was queued before the stop, and none came after it.
        self.stop_the_review_at_the_wait_cap(queued_message=True)

        self.assert_resume_takes_the_late_hand_back()

    def test_the_plan_edit_coders_open_choice_reaches_the_hand_back_and_the_prompt_says_where_it_goes(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it, drop the header")
        self.assertIn("OPEN CHOICE:", out)
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.hook("coder", "BEHAVIOR: plan rewritten\nOPEN CHOICE: add one more later step?", agent_id="p1")

        out = self.step("after-plan-edit")

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

        self.step("after-coder")

        said = say_path.read_text()
        self.assertNotIn("the first try", said)
        self.assertIn("Note: gate skipped", said)
        self.assertEqual(1, said.count("Implemented: "), said)
        self.assertEqual(1, said.count("Flagged: "), said)
        self.assertEqual(1, said.count("backend/src/orders.ts:3-5 - order matters"), said)
