"""Which checkout a /code run works in: every dispatch names the run's checkout, and a verb run from another checkout
goes on with the session's open run.

The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_checkout
"""
import json
import shutil
import unittest

import test_code_step as base


class CheckoutTest(base.CodeStepTest):
    def other_checkout(self, name="other"):
        # A second git repo with no /code state, as the session's cwd is when /code names another repo.
        checkout = self.tmp / name
        shutil.copytree(self.base_repo, checkout, symlinks=True)
        return checkout

    def checkout_sentence(self, checkout):
        return f"This run's checkout is {checkout.resolve()}. Read, edit and run commands only there"

    def test_a_run_started_in_a_repo_that_is_not_the_cwd_dispatches_its_coder_again_there_from_the_cwd(self):
        self.step("start", "--task", "fix the typo")
        self.age_dispatches(120)
        self.wait_env(5, "0.2")
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "resume").stdout

        self.assertIn("AGENT: coder", out)
        self.assertIn(self.checkout_sentence(self.repo), self.printed_prompt(out))
        self.assertFalse((cwd / ".git/code-step").exists())

    def test_status_from_another_checkout_shows_the_session_open_run(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "status").stdout

        self.assertEqual("coder", json.loads(out)["stage"])

    def test_a_verb_from_the_checkout_of_one_of_two_open_runs_stays_on_that_run(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        base.run(cwd, self.env, "start", "--task", "add retries")
        self.age_dispatches(120, cwd)
        self.wait_env(5, "0.2")

        out = base.run(cwd, self.env, "resume").stdout

        self.assertIn("Implement: add retries", out)
        self.assertIn(self.checkout_sentence(cwd), self.printed_prompt(out))

    def test_a_verb_from_outside_two_open_runs_stops_and_names_both_checkouts(self):
        self.step("start", "--task", "fix the typo")
        second_run = self.other_checkout()
        base.run(second_run, self.env, "start", "--task", "add retries")
        cwd = self.other_checkout("third")

        out = base.run(cwd, self.env, "resume").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn(f"- {self.repo.resolve()}", out)
        self.assertIn(f"- {second_run.resolve()}", out)
        self.assertNotIn("AGENT:", out)

    def test_a_run_of_another_session_is_not_followed_from_another_checkout(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-1"
        self.step("start", "--task", "fix the typo")
        state_path = self.repo / ".git/code-step/state.json"
        other_session_state = json.loads(state_path.read_text())
        other_session_state["sessionId"] = "sess-2"
        state_path.write_text(json.dumps(other_session_state))
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "status").stdout

        self.assertEqual("no code-step state", out.strip())

    def test_a_finished_run_is_not_followed_and_the_open_run_in_another_checkout_is(self):
        self.step("start", "--task", "fix the typo")
        state_path = self.repo / ".git/code-step/state.json"
        finished_state = json.loads(state_path.read_text())
        finished_state["stage"] = "done"
        state_path.write_text(json.dumps(finished_state))
        second_run = self.other_checkout()
        base.run(second_run, self.env, "start", "--task", "add retries")
        self.age_dispatches(120, second_run)
        self.wait_env(5, "0.2")
        third_checkout = self.other_checkout("third")

        out = base.run(third_checkout, self.env, "resume").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertIn(self.checkout_sentence(second_run), self.printed_prompt(out))

    def test_a_verb_from_another_checkout_clears_the_question_in_the_run_checkout(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\n  cause: plan\nPLAN-IMPACT: yes"
        out = self.coder_round(report)
        question_file = self.repo / ".git/code-step/question.md"
        self.assertIn("ACTION: ask-user", out)
        self.assertNotEqual("", question_file.read_text())
        cwd = self.other_checkout()

        base.run(cwd, self.env, "decide", "keep", "--by", "user", "--ruling", "keep it")

        self.assertEqual("", question_file.read_text())


def load_tests(loader, tests, pattern):
    # The tests of CodeStepTest run in test_code_step.py: this file runs its own.
    own_names = [name for name in loader.getTestCaseNames(CheckoutTest) if name in CheckoutTest.__dict__]
    return unittest.TestSuite(CheckoutTest(name) for name in own_names)


if __name__ == "__main__":
    unittest.main()
