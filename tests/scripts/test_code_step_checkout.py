"""Which checkout a /code run works in: every dispatch names the run's checkout, and a verb run from another checkout
goes on with the session's open run.

The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_checkout
"""
import json
import pathlib
import shutil
import unittest
import unittest.mock

import test_code_step as base
from test_code_step_cap_reached import CAP_WITH_ASK


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

    def leave_unreadable_state(self, checkout, state_text=None):
        # By default a state file with a key this code-step does not know, as a finished run of another session leaves.
        if state_text is None:
            state_text = json.dumps({"stage": "done", "sessionId": "sess-2", "packet": "x"})
        state_path = checkout / ".git/code-step/state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(state_text)

    def resume_run_repos_from(self, cwd):
        with unittest.mock.patch.dict("os.environ", {"HOME": str(self.home)}):
            return base.code_step_core.resume_run_repos(str(cwd), self.SESSION)

    def test_an_unreadable_state_in_the_cwd_checkout_does_not_block_the_open_run_in_another_checkout(self):
        self.step("start", "--task", "fix the typo")
        self.age_dispatches(120)
        self.wait_env(5, "0.2")
        cwd = self.other_checkout()
        self.leave_unreadable_state(cwd)

        out = base.run(cwd, self.env, "resume").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertIn(self.checkout_sentence(self.repo), self.printed_prompt(out))

    def test_an_unreadable_state_overwriting_the_sessions_run_in_cwd_checkout_does_not_block_the_run_elsewhere(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        base.run(cwd, self.env, "start", "--task", "add retries")
        self.age_dispatches(120)
        self.wait_env(5, "0.2")
        self.leave_unreadable_state(cwd)

        out = base.run(cwd, self.env, "resume").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertIn(self.checkout_sentence(self.repo), self.printed_prompt(out))

    def test_an_unreadable_state_in_a_subdirectory_cwd_checkout_does_not_hide_the_open_run_in_another_checkout(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        base.run(cwd, self.env, "start", "--task", "add retries")
        self.leave_unreadable_state(cwd)
        subdirectory = cwd / "nested"
        subdirectory.mkdir()

        with unittest.mock.patch.dict("os.environ", {"HOME": str(self.home)}):
            run_repos = base.code_step_core.resume_run_repos(str(subdirectory), self.SESSION)

        self.assertEqual([str(self.repo.resolve())], [str(pathlib.Path(repo).resolve()) for repo in run_repos])

    def test_an_unreadable_state_in_the_cwd_checkout_with_no_other_open_run_still_stops(self):
        cwd = self.other_checkout()
        self.leave_unreadable_state(cwd)

        out = base.run(cwd, self.env, "status").stdout

        self.assertIn("has keys this code-step does not know: packet", out)
        with self.assertRaises(base.code_step_state.StateFileError):
            self.resume_run_repos_from(cwd)

    def test_an_unreadable_state_of_the_sessions_own_open_run_with_another_open_run_elsewhere_still_stops(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        self.leave_unreadable_state(cwd, json.dumps({"stage": "coder", "sessionId": self.SESSION, "packet": "x"}))

        out = base.run(cwd, self.env, "status").stdout

        self.assertIn("has keys this code-step does not know: packet", out)
        with self.assertRaises(base.code_step_state.StateFileError):
            self.resume_run_repos_from(cwd)

    def test_an_unreadable_state_naming_no_session_with_another_open_run_elsewhere_still_stops(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        self.leave_unreadable_state(cwd, json.dumps({"stage": "coder", "packet": "x"}))

        with self.assertRaises(base.code_step_state.StateFileError) as raised:
            self.resume_run_repos_from(cwd)

        self.assertIn("has keys this code-step does not know: packet", str(raised.exception))

    def test_an_unreadable_state_naming_another_session_or_a_done_stage_goes_on_to_the_open_run_elsewhere(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        cases = {
            "another session": {"stage": "coder", "sessionId": "sess-2", "packet": "x"},
            "a done stage": {"stage": "done", "sessionId": self.SESSION, "packet": "x"},
        }
        for case, state in cases.items():
            with self.subTest(case):
                self.leave_unreadable_state(cwd, json.dumps(state))

                run_repos = self.resume_run_repos_from(cwd)

                self.assertEqual([str(self.repo.resolve())], [str(pathlib.Path(repo).resolve()) for repo in run_repos])

    def test_a_state_that_is_not_a_json_object_or_not_json_with_an_open_run_elsewhere_still_stops(self):
        self.step("start", "--task", "fix the typo")
        cwd = self.other_checkout()
        cases = {"[]": "does not hold a JSON object", "not json": "is not readable JSON"}
        for state_text, message in cases.items():
            with self.subTest(state_text):
                self.leave_unreadable_state(cwd, state_text)

                with self.assertRaises(base.code_step_state.StateFileError) as raised:
                    self.resume_run_repos_from(cwd)

                self.assertIn(message, str(raised.exception))

    def wait_at_asks(self, checkout):
        # The run of `checkout` waits for the user's rulings on one review ask.
        state_path = checkout / ".git/code-step/state.json"
        waiting_state = json.loads(state_path.read_text())
        waiting_state.update({"stage": "asks", "lane": "code", "iter": 1})
        waiting_state["asks"] = [{"finding": "a finding", "file_line": "src/widget.py:12", "question": "keep it?",
                                  "gate": "code-reviewer", "class": "bug"}]
        state_path.write_text(json.dumps(waiting_state))

    def stage_of(self, checkout):
        return json.loads((checkout / ".git/code-step/state.json").read_text())["stage"]

    def two_runs_and_a_cwd_in_neither(self):
        self.step("start", "--task", "fix the typo")
        second_run = self.other_checkout()
        base.run(second_run, self.env, "start", "--task", "add retries")
        return second_run, self.other_checkout("third")

    def test_asks_done_from_outside_two_open_runs_goes_on_with_the_one_run_at_its_asks(self):
        second_run, cwd = self.two_runs_and_a_cwd_in_neither()
        self.wait_at_asks(second_run)

        result = base.run(cwd, self.env, "asks-done", "accepted")

        self.assertNotIn("open /code run in each", result.stdout)
        self.assertEqual("coder", self.stage_of(self.repo))
        self.assertEqual("asks-coder", self.stage_of(second_run), result.stdout + result.stderr)

    def test_asks_done_from_outside_two_runs_at_their_asks_names_both_checkouts_and_repo(self):
        second_run, cwd = self.two_runs_and_a_cwd_in_neither()
        self.wait_at_asks(self.repo)
        self.wait_at_asks(second_run)

        out = base.run(cwd, self.env, "asks-done", "rejected").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn(f"- {self.repo.resolve()}", out)
        self.assertIn(f"- {second_run.resolve()}", out)
        self.assertIn("--repo <checkout>", out)
        self.assertEqual("asks", self.stage_of(second_run))

    def test_asks_done_with_repo_runs_on_that_checkout_from_a_cwd_in_neither(self):
        second_run, cwd = self.two_runs_and_a_cwd_in_neither()
        self.wait_at_asks(self.repo)
        self.wait_at_asks(second_run)

        out = base.run(cwd, self.env, "asks-done", "--repo", str(second_run), "accepted").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertEqual("asks", self.stage_of(self.repo))
        self.assertEqual("asks-coder", self.stage_of(second_run))

    def test_asks_done_with_repo_from_inside_another_open_runs_checkout_rules_on_the_named_run(self):
        second_run, _ = self.two_runs_and_a_cwd_in_neither()
        self.wait_at_asks(self.repo)
        self.wait_at_asks(second_run)

        base.run(self.repo, self.env, "asks-done", "--repo", str(second_run), "accepted")

        self.assertEqual("asks-coder", self.stage_of(second_run))
        self.assertEqual("asks", self.stage_of(self.repo))

    def test_a_verb_other_than_asks_done_from_outside_two_runs_stops_even_with_one_at_asks(self):
        second_run, cwd = self.two_runs_and_a_cwd_in_neither()
        self.wait_at_asks(second_run)

        out = base.run(cwd, self.env, "resume").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn(f"- {self.repo.resolve()}", out)
        self.assertIn(f"- {second_run.resolve()}", out)
        self.assertEqual("asks", self.stage_of(second_run))

    def test_asks_done_with_repo_of_a_checkout_without_an_open_run_stops(self):
        self.step("start", "--task", "fix the typo")
        self.wait_at_asks(self.repo)
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "asks-done", "--repo", str(cwd), "rejected").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn("holds no open /code run", out)

    def test_asks_done_with_repo_from_another_session_goes_on_with_the_open_run(self):
        self.step("start", "--task", "fix the typo")
        self.wait_at_asks(self.repo)
        cwd = self.other_checkout()
        other_session_env = {**self.env, "CLAUDE_CODE_SESSION_ID": "sess-after-clear"}

        out = base.run(cwd, other_session_env, "asks-done", "--repo", str(self.repo), "accepted").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertEqual("asks-coder", self.stage_of(self.repo))

    def test_asks_done_with_repo_of_a_run_that_is_done_stops_and_keeps_its_stage(self):
        self.step("start", "--task", "fix the typo")
        self.wait_at_asks(self.repo)
        state_path = self.repo / ".git/code-step/state.json"
        done_state = json.loads(state_path.read_text())
        done_state["stage"] = "done"
        state_path.write_text(json.dumps(done_state))
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "asks-done", "--repo", str(self.repo), "rejected").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn("holds no open /code run", out)
        self.assertEqual("done", self.stage_of(self.repo))

    def test_asks_done_with_a_bad_repo_value_stops_and_leaves_the_run_at_its_asks(self):
        self.step("start", "--task", "fix the typo")
        self.wait_at_asks(self.repo)
        cwd = self.other_checkout()
        bad_repo_args = (["asks-done", "rejected", "--repo"],
                         ["asks-done", "--repo", str(self.tmp / "missing"), "rejected"])

        for args in bad_repo_args:
            with self.subTest(args=args):
                out = base.run(cwd, self.env, *args).stdout

                self.assertIn("ACTION: stop", out)
                self.assertIn("is not a path inside a git repo", out)
                self.assertEqual("asks", self.stage_of(self.repo))

    def test_asks_done_from_outside_two_open_runs_neither_at_asks_stops_and_names_both_checkouts(self):
        second_run, cwd = self.two_runs_and_a_cwd_in_neither()

        out = base.run(cwd, self.env, "asks-done", "accepted").stdout

        self.assertIn("ACTION: stop", out)
        self.assertIn(f"- {self.repo.resolve()}", out)
        self.assertIn(f"- {second_run.resolve()}", out)
        self.assertEqual("coder", self.stage_of(self.repo))
        self.assertEqual("coder", self.stage_of(second_run))

    def test_correct_ruling_with_repo_from_another_checkout_records_the_correction(self):
        self.begin_asks_coder("accepted")
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "correct-ruling", "--repo", str(self.repo), "rejected").stdout

        self.assertNotIn("ACTION: stop", out)
        self.assertIn("correction", self.said())
        self.assertEqual("asks-coder", self.stage_of(self.repo))

    def test_correct_ruling_with_repo_from_another_checkout_at_the_asks_stage_dispatches_the_asks_coder(self):
        self.step("start", "--task", "fix the typo")
        self.wait_at_asks(self.repo)
        cwd = self.other_checkout()

        out = base.run(cwd, self.env, "correct-ruling", "--repo", str(self.repo), "accepted").stdout

        self.assertIn("AGENT: coder", out)
        self.assertEqual("asks-coder", self.stage_of(self.repo))

    def test_the_asks_hand_back_names_the_repo_of_the_run_in_its_asks_done_line(self):
        self.coder_round()
        self.hook("review-loop", CAP_WITH_ASK, agent_id="r1")

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"`asks-done --repo {self.repo.resolve()} accepted modified", self.said())

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
