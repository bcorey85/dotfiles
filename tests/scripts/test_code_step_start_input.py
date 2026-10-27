"""What `start` of code_step.py reads from its arguments: a task file, run notes after a phase, a plan file outside the
repo, a restart over an open run, and the refusal of an Automated Verification line that cannot run.

The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_start_input
"""
import shlex
import time
import unittest

import test_code_step as base

HOOK_SENSITIVE_TASK = "decide: wrap `sudo -u deploy` and a '-c' flag; each case's new rule stays \"quoted\""
COMPOUND_LINE = "- [ ] **Check**: totals - `TMP=$(mktemp -d) && npx vitest run \"$TMP\"`"
SHELL_WRAPPER = "-c '"


class StartInputTest(base.CodeStepTest):
    def write_outside_file(self, name, text):
        outside = self.tmp / "scratchpad"
        outside.mkdir(exist_ok=True)
        path = outside / name
        path.write_text(text)
        return path

    def args_of_printed_command(self, out, verb_words):
        # The arguments a printed `code_step.py <verb words> ...` line would pass, as the shell reads them.
        command_line = next(line for line in out.splitlines() if f"code_step.py {verb_words}" in line)
        command_text = command_line.split("code_step.py", 1)[1].strip().strip("`")
        return shlex.split(command_text)

    def stop_the_coder_on_its_report(self):
        self.start_phase_one()
        self.set_state(stage="stopped", resumableCoderId="a1", resumableCoderAt=time.time(), dispatchAt=None)

    # ---------- --task-file ----------

    def test_task_file_text_reaches_the_coder_unchanged(self):
        task_file = self.write_outside_file("brief.md", HOOK_SENSITIVE_TASK + "\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"Implement: {HOOK_SENSITIVE_TASK}\nsecond line\n", out)
        self.assertIsNone(self.state().get("plan"))

    def test_task_file_that_is_missing_or_empty_exits_two_and_changes_nothing(self):
        empty_file = self.write_outside_file("empty.md", "  \n")
        for task_file in (self.tmp / "nope.md", empty_file):
            with self.subTest(task_file=task_file):
                finished = base.run(self.repo, self.env, "start", "--task-file", str(task_file))

                self.assertEqual(2, finished.returncode)
                self.assertIn(str(task_file), finished.stderr)
                self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_task_file_flag_without_a_path_exits_two(self):
        finished = base.run(self.repo, self.env, "start", "--task-file")

        self.assertEqual(2, finished.returncode)
        self.assertIn("--task-file needs a path", finished.stderr)

    def test_a_positional_file_outside_the_repo_that_is_no_plan_is_refused_with_the_task_file_command(self):
        task_file = self.write_outside_file("brief.md", "Add retries to the orders client.\n")

        out = self.step("start", str(task_file))

        self.assertTrue(out.startswith("Refused: "), out)
        self.assertIn("ACTION: rerun", out)
        self.assertIn(f"COMMAND: {self.own_command('start --task-file ' + str(task_file))}", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_the_command_printed_for_a_file_outside_the_repo_starts_the_coder_with_its_text(self):
        task_file = self.write_outside_file("brief.md", "Add retries to the orders client.\n")
        refused = self.step("start", str(task_file))

        out = self.step(*self.args_of_printed_command(refused, "start --task-file"))

        self.assertIn("Implement: Add retries to the orders client.", out)

    def test_a_plan_file_outside_the_repo_still_asks_for_a_plan_inside_it(self):
        plan_file = self.write_outside_file("spec.md", base.PLAN)

        out = self.step("start", str(plan_file))

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("outside the repo", (self.repo / ".git/code-step/question.md").read_text())

    def test_start_help_names_the_task_file_and_the_run_notes(self):
        finished = base.run(self.repo, self.env, "start", "--help")

        self.assertEqual(0, finished.returncode)
        self.assertIn("--task-file <path>", finished.stdout)
        self.assertIn("run notes", finished.stdout)

    # ---------- run notes ----------

    def test_text_after_a_plan_and_a_phase_flag_reaches_the_coder_as_run_notes(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2", "only", "touch", "totals; no console.log")

        self.assertIn("AGENT: coder", out)
        self.assertIn("Run notes from the user.", out)
        self.assertIn("only touch totals; no console.log", out)
        self.assertEqual("2", self.state()["phase"])

    def test_text_after_a_plan_and_the_words_phase_and_an_id_reaches_the_coder_as_run_notes(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "Phase", "2", "only", "touch", "totals")

        self.assertIn("AGENT: coder", out)
        self.assertIn("only touch totals", out)
        self.assertEqual("2", self.state()["phase"])

    def test_a_phase_run_with_no_trailing_text_has_no_run_notes_in_the_brief(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2")

        self.assertNotIn("Run notes", out)

    def test_run_notes_on_a_closing_phase_stop_and_say_they_were_not_passed_on(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "4", "keep", "it", "short")

        self.assertIn("ACTION: stop", out)
        self.assertIn("takes no run notes", out)

    # ---------- restart ----------

    def test_the_restart_command_printed_for_task_text_over_an_open_run_runs(self):
        self.coder_round()
        refused = self.step("start", "fix", "the", "typo")

        out = self.step(*self.args_of_printed_command(refused, "start --restart"))

        self.assertIn("Implement: fix the typo", out)

    def test_a_restart_that_stops_on_a_phase_check_leaves_no_open_run(self):
        self.coder_round()

        stopped = self.step("start", "--restart", self.plan, "--phase", "9")
        next_start = self.step("start", "--task", "fix the typo")

        self.assertIn("ACTION: stop", stopped)
        self.assertIn("AGENT: coder", next_start)

    def test_a_run_stopped_on_the_coder_report_is_replaced_by_the_same_session_without_restart(self):
        self.stop_the_coder_on_its_report()

        out = self.step("start", "--task", "answer the design questions")

        self.assertIn("AGENT: coder", out)
        self.assertIn("Implement: answer the design questions", out)

    def test_a_run_stopped_on_the_coder_report_is_still_refused_to_another_session(self):
        self.stop_the_coder_on_its_report()
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-2"

        out = self.step("start", "--task", "answer the design questions")

        self.assertTrue(out.startswith("Refused: "), out)

    # ---------- verification line that cannot run ----------

    def test_a_compound_verification_line_names_its_phase_and_offers_only_an_executable_script(self):
        plan_text = base.PLAN.replace(
            "Audit trail\n\n**File**: `backend/src/audit.ts`\n",
            "Audit trail\n\n**File**: `backend/src/audit.ts`\n\n#### Automated Verification:\n\n"
            f"{COMPOUND_LINE}\n")
        (self.repo / self.plan).write_text(plan_text)

        out = self.start_phase_one()

        self.assertIn("ACTION: stop", out)
        self.assertIn("3: - [ ] **Check**: totals", out)
        self.assertIn("executable repo script", out)
        self.assertIn("later phase's line stops the first phase's start", out)
        self.assertNotIn(SHELL_WRAPPER, out)


def load_tests(loader, tests, pattern):
    # The tests of CodeStepTest run in test_code_step.py: this file runs its own.
    own_names = [name for name in loader.getTestCaseNames(StartInputTest) if name in StartInputTest.__dict__]
    return unittest.TestSuite(StartInputTest(name) for name in own_names)


if __name__ == "__main__":
    unittest.main()
