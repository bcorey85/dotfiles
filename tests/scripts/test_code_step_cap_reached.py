"""What a /code run does after its review loop stops at the round cap with findings still open: the user's rulings on
its asks, or `review-again` when it has none, send the open findings to one more review-loop pass.

The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_cap_reached
"""
import unittest

import test_code_step as base

CAP = ('status: cap-reached\niter: 2\nfixed: []\nfindings_remaining:\n'
       '- {finding: "the rounding stays open", file_line: "backend/src/orders.ts:1"}\n')
CAP_WITH_ASK = CAP + base.CodeStepTest.ASK.split("\n", 3)[3] + "\n"
BLOCKER_WITH_ASK = ('status: critical-blocker\niter: 1\nblockers:\n'
                    '- {finding: "the rounding is broken", file_line: "backend/src/orders.ts:1"}\n'
                    + base.CodeStepTest.ASK.split("\n", 3)[3] + "\n")


class CapReachedTest(base.CodeStepTest):
    def cap_round(self, packet):
        self.coder_round()
        self.hook("review-loop", packet, agent_id="r1")
        return self.step("resume")

    def converge(self):
        self.hook("review-loop", self.LOOP_OK, agent_id="r2")
        return self.step("resume")

    def test_a_cap_reached_stop_with_an_ask_sends_the_ruling_and_the_open_findings_to_one_more_review_that_converges(
            self):
        out = self.cap_round(CAP_WITH_ASK)

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("the rounding stays open", self.said())
        self.assertIsNone(self.gate_mark())

        out = self.step("asks-done", "rejected")

        prompt = self.printed_prompt(out)
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("carried-findings:", prompt)
        self.assertIn("finding: the rounding stays open", prompt)
        self.assertIn("f - keep? (backend/src/orders.ts:2): rejected", prompt)
        self.assertIn("iter: 0", prompt)
        self.assertNotIn("ask: ", prompt.split("carried-findings:", 1)[1].split("ruled-asks", 1)[0])
        self.assertEqual(self.state()["iter"], 0)
        [outcome_line] = self.finding_log_lines()
        self.assertIn("iter=2", outcome_line)

        out = self.converge()

        self.assert_marked_clean(out)
        self.assert_first_phase_ticked()

    def test_asks_done_with_the_wrong_number_of_outcomes_names_how_many_it_expects(self):
        self.cap_round(CAP_WITH_ASK)

        out = self.step("asks-done", "accepted", "rejected")

        self.assertIn("1 ask(s) wait: give 1 outcome(s), in order.", out)

    def test_a_cap_reached_stop_with_an_accepted_ask_sends_the_open_findings_to_the_review_after_the_asks_coder(self):
        self.cap_round(CAP_WITH_ASK)

        out = self.step("asks-done", "accepted")

        self.assertIn("AGENT: coder", out)
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: o is a const", agent_id="c2")
        out = self.step("resume")
        prompt = self.printed_prompt(out)
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("finding: the rounding stays open", prompt)
        self.assertIn("iter: 0", prompt)

    def test_a_docs_only_asks_coder_after_a_stop_with_an_ask_still_gets_one_more_review_with_the_carried_item(self):
        stops = [
            ("cap", CAP_WITH_ASK, "finding: the rounding stays open"),
            ("critical blocker", BLOCKER_WITH_ASK, "the rounding is broken"),
        ]
        for label, packet, carried_text in stops:
            with self.subTest(label):
                self.setUp()
                self.cap_round(packet)
                self.step("asks-done", "accepted")
                (self.repo / "docs").mkdir(exist_ok=True)
                (self.repo / "docs/notes.md").write_text("a note\n")
                self.hook("coder", "BEHAVIOR: a note", agent_id="c2")

                out = self.step("resume")

                prompt = self.printed_prompt(out)
                self.assertIn("AGENT: review-loop", out)
                self.assertIn(carried_text, prompt)

    def test_the_review_after_an_asks_coder_that_touched_other_files_still_covers_the_carried_item_file(self):
        stops = [("cap", CAP_WITH_ASK), ("critical blocker", BLOCKER_WITH_ASK)]
        for label, packet in stops:
            with self.subTest(label):
                self.setUp()
                self.cap_round(packet)
                self.step("asks-done", "accepted")
                (self.repo / "backend/src/other.ts").write_text("export const x = 1\n")
                self.hook("coder", "BEHAVIOR: x is a const", agent_id="c2")

                out = self.step("resume")

                prompt = self.printed_prompt(out)
                self.assertIn("AGENT: review-loop", out)
                self.assertIn("- path: backend/src/orders.ts", prompt)
                self.assertIn("- path: backend/src/other.ts", prompt)

    def test_a_cap_reached_stop_without_asks_takes_review_again_for_one_more_review_that_converges(self):
        out = self.cap_round(CAP)

        self.assertIn("ACTION: stop", out)
        self.assertIn("`review-again`", self.said())
        self.assertIsNone(self.gate_mark())

        out = self.step("review-again")

        prompt = self.printed_prompt(out)
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("finding: the rounding stays open", prompt)
        self.assertIn("iter: 0", prompt)

        out = self.converge()

        self.assert_marked_clean(out)
        self.assert_first_phase_ticked()

    def test_review_again_after_a_cap_skips_the_structure_pass_on_the_same_diff(self):
        self.cap_round(CAP)

        out = self.step("review-again")

        self.assertIn("structure-pass: skip", self.printed_prompt(out))

    def test_a_second_cap_after_the_carried_pass_stops_for_a_restart_with_no_review_again(self):
        self.cap_round(CAP)
        self.step("review-again")
        self.hook("review-loop", CAP, agent_id="r2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        question = (self.repo / ".git/code-step/question.md").read_text()
        self.assertIn("start --restart", question)
        self.assertNotIn("review-again", question)
        self.assertIn("Refused", self.step("review-again"))

    def test_a_second_cap_with_an_ask_after_the_carried_pass_stops_for_a_restart_with_no_asks_route(self):
        self.cap_round(CAP_WITH_ASK)
        self.step("asks-done", "rejected")
        self.hook("review-loop", CAP_WITH_ASK, agent_id="r2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertNotEqual("asks", self.state()["stage"])

    def test_a_critical_blocker_stop_with_an_ask_lets_asks_done_record_it_and_carries_the_blocker_to_one_more_review(
            self):
        out = self.cap_round(BLOCKER_WITH_ASK)

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("the rounding is broken", self.said())
        self.assertIsNone(self.gate_mark())

        out = self.step("asks-done", "rejected")

        prompt = self.printed_prompt(out)
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("the rounding is broken", prompt)
        self.assertIn("f - keep? (backend/src/orders.ts:2): rejected", prompt)

    def test_a_second_critical_blocker_with_an_ask_after_a_preset_rejection_stops_with_no_human_loop(self):
        self.env["CODE_STEP_ASKS_OUTCOME"] = "rejected"
        out = self.cap_round(BLOCKER_WITH_ASK)
        self.assertIn("AGENT: review-loop", out)
        self.hook("review-loop", BLOCKER_WITH_ASK, agent_id="r2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertEqual("critical-blocker", self.state()["stopReason"])
        self.assertIn("Open questions:\n- f - keep? (backend/src/orders.ts:2)", out)

    def test_resume_at_a_cap_reached_stop_names_review_again(self):
        self.cap_round(CAP)

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("`review-again`", self.said())


def load_tests(loader, tests, pattern):
    # The tests of CodeStepTest run in test_code_step.py: this file runs its own.
    own_names = [name for name in loader.getTestCaseNames(CapReachedTest) if name in CapReachedTest.__dict__]
    return unittest.TestSuite(CapReachedTest(name) for name in own_names)


if __name__ == "__main__":
    unittest.main()
