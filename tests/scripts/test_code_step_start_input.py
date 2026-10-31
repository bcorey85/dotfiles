"""What `start` of code_step.py reads from its arguments: a task file, run notes after a phase or a plan, a plan file
outside the repo, a restart over an open run, and the refusal of an Automated Verification line that cannot run.

The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_start_input
"""
import json
import pathlib
import shlex
import shutil
import tempfile
import time
import unittest

import test_code_step as base

# isort: split
import code_step_start
import code_step_start_args

HOOK_SENSITIVE_TASK = "decide: wrap `sudo -u deploy` and a '-c' flag; each case's new rule stays \"quoted\""
COMPOUND_LINE = "- [ ] **Check**: totals - `TMP=$(mktemp -d) && npx vitest run \"$TMP\"`"
SHELL_WRAPPER = "-c '"
SESSION_PHASE_TEXT = ("## Phase 2: Mutation check\n\n**Session phase**: `mutation-tester`\n\n"
                      "1. Dispatch `mutation-tester`.\n2. Commit.\n")
RUN_NOTES_HEADING = "Run notes from the user. They bind this run; the plan stays the spec:"


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
        self.set_state(stage="stopped", stop={"kind": "coder-resumable", "at": time.time(), "agentId": "a1"},
                       dispatchAt=None)

    # ---------- --task-file ----------

    def test_task_file_text_reaches_the_coder_unchanged(self):
        task_file = self.write_outside_file("brief.md", HOOK_SENSITIVE_TASK + "\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"Implement: {HOOK_SENSITIVE_TASK}\nsecond line\n", out)
        self.assertIsNone(self.state().get("plan"))

    def test_a_task_file_that_opens_with_the_plan_starts_a_plan_run_with_the_rest_as_run_notes(self):
        notes = "— From x (orchestrator): only touch orders (not totals); keep it small\nsecond line"
        for task_text in (f"{self.plan} {notes}\n", f"Repo: {self.repo}\n\n{self.plan} {notes}\n"):
            with self.subTest(task_text=task_text):
                (self.repo / ".git/code-step/state.json").unlink(missing_ok=True)
                task_file = self.write_outside_file("brief.md", task_text)

                out = self.step("start", "--task-file", str(task_file))

                self.assertIn("AGENT: coder", out)
                self.assertEqual(self.plan, self.state()["plan"])
                self.assertEqual("1", self.state()["phase"])
                self.assertIn(f"{RUN_NOTES_HEADING}\n{notes}", out)
                self.assertNotIn("Repo:", out)

    def test_a_task_file_that_opens_with_the_plan_and_a_phase_lead_runs_that_phase(self):
        task_file = self.write_outside_file("brief.md", f"{self.plan} Phase 2 touch totals\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertEqual("2", self.state()["phase"])
        self.assertEqual("2", self.state()["onlyPhase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\ntouch totals\nsecond line", out)

    def test_a_task_file_that_opens_with_the_plan_and_a_phase_flag_runs_that_phase(self):
        task_file = self.write_outside_file("brief.md", f"{self.plan} --phase 2 touch totals\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertEqual("2", self.state()["phase"])
        self.assertEqual("2", self.state()["onlyPhase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\ntouch totals\nsecond line", out)

    def test_start_phase_flag_with_a_task_file_on_a_fresh_run_runs_that_phase_with_the_notes(self):
        task_file = self.write_outside_file("brief.md", f"{self.plan} touch totals\n")

        out = self.step("start", "--phase", "2", "--task-file", str(task_file))

        self.assertEqual("2", self.state()["phase"])
        self.assertEqual("2", self.state()["onlyPhase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\ntouch totals", out)

    def test_a_task_file_that_opens_with_a_ticket_id_and_a_phase_lead_runs_that_ticket_plan_phase(self):
        shutil.copytree(self.repo / "docs/plans/orders", self.repo / "docs/plans/ABC-400-x")
        task_file = self.write_outside_file("brief.md", "ABC-400 Phase 1 only touch orders\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertEqual("docs/plans/ABC-400-x/spec.md", self.state()["plan"])
        self.assertEqual("1", self.state()["phase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\nonly touch orders\nsecond line", out)

    def test_a_task_file_that_opens_with_a_ticket_id_and_no_phase_stays_planless(self):
        shutil.copytree(self.repo / "docs/plans/orders", self.repo / "docs/plans/ABC-400-x")
        task_file = self.write_outside_file("brief.md", "ABC-400 is broken\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIsNone(self.state().get("plan"))
        self.assertIn("Implement: ABC-400 is broken", out)

    def test_a_task_file_with_an_indented_repo_line_stays_planless_in_this_checkout_with_the_text_unchanged(self):
        other = self.other_repo()
        task_text = f"  Repo: {other}\n{self.plan} notes\n"
        task_file = self.write_outside_file("brief.md", task_text)

        out = self.step("start", "--task-file", str(task_file))

        self.assertNotIn(f"This run's checkout is {other}", out)
        self.assertFalse((other / ".git/code-step/state.json").exists())
        self.assertIsNone(self.state().get("plan"))
        self.assertIn(f"Implement: {task_text}", out)

    def test_a_task_file_that_opens_with_the_plan_and_a_phase_lead_keeps_the_notes_line_breaks(self):
        task_file = self.write_outside_file("brief.md", f"{self.plan} Phase 1 only touch orders\nsecond line\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertEqual(self.plan, self.state()["plan"])
        self.assertEqual("1", self.state()["phase"])
        self.assertEqual("1", self.state()["onlyPhase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\nonly touch orders\nsecond line", out)

    def test_a_task_file_that_opens_with_a_markdown_file_that_has_no_phases_stays_planless(self):
        (self.repo / "README.md").write_text("# Readme\n\nSome words.\n")
        task_file = self.write_outside_file("brief.md", "README.md needs a new intro\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIsNone(self.state().get("plan"))
        self.assertIn("Implement: README.md needs a new intro", out)

    def test_a_task_file_with_a_repo_line_runs_the_plan_of_that_other_checkout(self):
        other = self.other_repo()
        (self.repo / self.plan).unlink()
        task_file = self.write_outside_file("brief.md", f"Repo: {other}\n{self.plan} only touch orders\n")

        out = self.step("start", "--task-file", str(task_file))

        other_state = json.loads((other / ".git/code-step/state.json").read_text())
        self.assertIn(f"This run's checkout is {other}", out)
        self.assertEqual(self.plan, other_state["plan"])
        self.assertEqual("1", other_state["phase"])
        self.assertIn(f"{RUN_NOTES_HEADING}\nonly touch orders", out)

    def test_a_task_file_that_does_not_open_with_a_plan_stays_planless(self):
        task_file = self.write_outside_file("brief.md", f"add orders, see {self.plan}\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIn("AGENT: coder", out)
        self.assertIsNone(self.state().get("plan"))
        self.assertIn(f"Implement: add orders, see {self.plan}", out)

    def test_task_text_that_opens_with_the_plan_stays_planless(self):
        out = self.step("start", "--task", f"{self.plan} — notes")

        self.assertIn("AGENT: coder", out)
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

    def test_a_task_file_that_opens_with_a_plan_outside_the_repo_asks_for_a_plan_inside_it(self):
        plan_file = self.write_outside_file("spec.md", base.PLAN)
        task_file = self.write_outside_file("brief.md", f"{plan_file} only touch orders\n")

        out = self.step("start", "--task-file", str(task_file))

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("outside the repo", (self.repo / ".git/code-step/question.md").read_text())

    def test_run_notes_after_a_plan_outside_the_repo_and_its_phase_reach_the_question(self):
        plan_file = self.write_outside_file("spec.md", base.PLAN)

        out = self.step("start", str(plan_file), "--phase", "1", "only", "touch", "orders")

        self.assertIn("ACTION: ask-user", out)
        question = (self.repo / ".git/code-step/question.md").read_text()
        self.assertIn("outside the repo", question)
        self.assertIn("only touch orders", question)

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

    def test_a_brief_after_a_plan_with_no_phase_starts_the_next_phase_with_it_as_run_notes(self):
        for brief_words in (["—", "only", "touch", "orders"], ["— only touch orders"]):
            with self.subTest(brief_words=brief_words):
                (self.repo / ".git/code-step/state.json").unlink(missing_ok=True)

                out = self.step("start", self.plan, *brief_words)

                self.assertIn("AGENT: coder", out)
                self.assertIn(f"{RUN_NOTES_HEADING}\n— only touch orders", out)
                self.assertEqual("1", self.state()["phase"])

    def test_text_after_an_in_repo_markdown_file_that_is_no_plan_is_not_taken_as_run_notes(self):
        (self.repo / "README.md").write_text("# Readme\n")

        out = self.step("start", "README.md", "typo")

        self.assertTrue(out.startswith("Refused: "), out)
        self.assertNotIn("AGENT: coder", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_text_after_a_brief_outside_the_repo_keeps_the_refusal_that_drops_no_words_silently(self):
        task_file = self.write_outside_file("brief.md", "Add retries to the orders client.\n")

        out = self.step("start", str(task_file), "Add", "retries")

        self.assertTrue(out.startswith("Refused: "), out)
        self.assertIn("The text after it was not passed to the coder.", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_two_plan_files_with_text_and_no_phase_do_not_start_a_run_on_the_first(self):
        second_plan = self.repo / "second.md"
        second_plan.write_text(base.PLAN)

        out = self.step("start", self.plan, str(second_plan), "only", "touch", "orders")

        self.assertNotIn("Run notes from the user.", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_two_plan_files_with_a_phase_flag_and_text_do_not_start_a_run_on_the_first(self):
        second_plan = self.repo / "second.md"
        second_plan.write_text(base.PLAN)

        out = self.step("start", self.plan, str(second_plan), "--phase", "1", "only", "touch", "orders")

        self.assertNotIn("Run notes from the user.", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_text_after_a_plan_file_outside_the_repo_is_refused_and_kept_in_the_output(self):
        plan_file = self.write_outside_file("spec.md", base.PLAN)

        out = self.step("start", str(plan_file), "only", "touch", "orders")

        self.assertTrue(out.startswith("Refused: "), out)
        self.assertIn("only touch orders", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_a_phase_run_with_no_trailing_text_has_no_run_notes_in_the_brief(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2")

        self.assertNotIn("Run notes", out)

    def test_run_notes_on_a_closing_phase_reach_the_skill_it_invokes(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "4", "build", "with", "two", "jobs")

        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("Run notes from the user. They bind this run; the plan stays the spec:\nbuild with two jobs", out)

    # ---------- session-only phase ----------

    def test_a_phase_with_a_session_phase_line_stops_for_the_session_and_closes_with_session_done(self):
        session_phase = ("## Phase 2: Mutation check\n\n**Session phase**: mutation-tester\n\n"
                         "1. Dispatch the `mutation-tester` agent on "
                         "`backend/src/orders.ts`.\n2. Record its lines in the plan.\n3. Commit.\n")
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        self.assertIn(old_phase, self.plan_text())
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        (self.repo / "dirty-before-start.txt").write_text("left over\n")

        out = self.step("start", self.plan, "--phase", "2")

        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Dispatch the `mutation-tester` agent yourself", out)
        self.assertIn("invoke Skill code with `session-done 2`", out)
        self.assertNotIn("`tick`", out)
        self.assertEqual("session", self.state()["stage"])
        self.assertIn("- [ ] Phase 2:", self.plan_text())

        (self.repo / "mutation-report.txt").write_text("done\n")
        closed = self.step("session-done", "2")

        self.assertIn("- [x] Phase 2:", self.plan_text())
        self.assertIn("Phase 2 marked done", closed)
        commit_line = next(line for line in self.said().splitlines() if "git add -- " in line)
        self.assertIn("mutation-report.txt", commit_line)
        self.assertNotIn("dirty-before-start.txt", commit_line)
        self.assertIn("docs/plans/orders/spec.md", self.said())
        self.assertNotIn("marked done with `tick`", self.plan_text())

    def test_verify_after_a_session_phase_failed_its_checks_closes_it_with_no_review_gate(self):
        session_phase = (SESSION_PHASE_TEXT + "\n"
                         "#### Automated Verification:\n\n"
                         "- [ ] **Tests**: report exists - `test -f mutation-report.txt`\n")
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")

        failed = self.step("session-done", "2")

        self.assertIn("Automated Verification failed", failed)
        self.assertEqual("verification", self.state()["stop"]["kind"])
        self.assertIn("- [ ] Phase 2:", self.plan_text())

        (self.repo / "mutation-report.txt").write_text("done\n")
        closed = self.step("verify")

        self.assertIn("- [x] Phase 2:", self.plan_text())
        self.assertIn("Phase 2 marked done", closed)
        self.assertIn("git add -- ", self.said())

    def test_resume_on_a_session_phase_says_its_steps_again(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")

        out = self.step("resume")

        self.assertIn("Dispatch the `mutation-tester` agent yourself", out)
        self.assertIn("`session-done 2`", out)

    def test_resume_asks_about_the_saved_state_when_the_phase_is_no_longer_session_only(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")
        (self.repo / self.plan).write_text(self.plan_text().replace(session_phase, old_phase))

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("The run is at stage session", self.said())

    def test_resume_asks_about_the_saved_state_when_the_plan_of_a_session_phase_is_gone(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")
        (self.repo / self.plan).unlink()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("The run is at stage session", self.said())

    def test_restarting_an_open_session_phase_keeps_its_earlier_edits_in_the_commit_line(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")
        original_base_head = self.state()["baseHead"]
        (self.repo / "earlier-edit.txt").write_text("done\n")

        self.step("start", "--restart", self.plan, "--phase", "2")
        self.assertEqual(original_base_head, self.state()["baseHead"])
        self.step("session-done", "2")

        commit_line = next(line for line in self.said().splitlines() if "git add -- " in line)
        self.assertIn("earlier-edit.txt", commit_line)

    def test_restarting_onto_a_different_session_phase_does_not_reuse_the_earlier_phases_baseline(self):
        session_phase = SESSION_PHASE_TEXT
        second_session_phase = SESSION_PHASE_TEXT.replace("Phase 2: Mutation check", "Phase 3: Second check")
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        old_third_phase = "## Phase 3: Audit trail\n\n**File**: `backend/src/audit.ts`\n"
        plan_text = self.plan_text().replace(old_phase, session_phase)
        self.assertIn(old_third_phase, plan_text)
        (self.repo / self.plan).write_text(plan_text.replace(old_third_phase, second_session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")
        (self.repo / "phase-two-edit.txt").write_text("done\n")

        self.step("start", "--restart", self.plan, "--phase", "3")
        self.step("session-done", "3")

        commit_line = next(line for line in self.said().splitlines() if "git add -- " in line)
        self.assertNotIn("phase-two-edit.txt", commit_line)

    def test_the_session_stop_prints_the_plan_lines_of_a_phase_the_session_phase_reuses(self):
        session_phase = SESSION_PHASE_TEXT + "\nMutants: same as Phase 1.\n"
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2")

        self.assertIn("ACTION: stop", out)
        self.assertRegex(out, rf"Phase 1, which Phase 2 reuses: {self.plan} lines \d+-\d+\.")

    def test_restarting_a_session_phase_after_a_reset_takes_a_fresh_start_commit_and_keeps_the_baseline(self):
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, SESSION_PHASE_TEXT))
        self.finish_phase_one()
        self.commit_all()
        self.git("commit", "-q", "--allow-empty", "-m", "empty")
        self.step("start", self.plan, "--phase", "2")
        (self.repo / "earlier-edit.txt").write_text("done\n")
        started = self.state()
        self.git("reset", "-q", "HEAD~1")

        self.step("start", "--restart", self.plan, "--phase", "2")

        restarted = self.state()
        self.assertEqual("session", restarted["stage"])
        self.assertNotEqual(started["baseHead"], restarted["baseHead"])
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), restarted["baseHead"])
        self.assertEqual(started["baseline"], restarted["baseline"])

    def test_a_session_phase_line_naming_a_coder_with_no_file_entry_still_goes_to_the_coder(self):
        coder_phase = "## Phase 2: Totals\n\n**Session phase**: `coder`\n\n1. Dispatch `coder`.\n2. Commit.\n"
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, coder_phase))
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2")

        self.assertIn("AGENT: coder", out)
        self.assertNotIn("yourself", out)
        self.assertNotIn("session-done", out)

    def test_session_done_runs_only_on_a_session_phase(self):
        self.start_phase_one()

        refused = self.step("session-done", "1")

        self.assertIn("session-done ran with no session phase pending.", refused)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_session_done_with_no_open_run_is_refused_names_itself_and_writes_no_state(self):
        refused = self.step("session-done", "2")

        self.assertTrue(refused.startswith("Refused: "), refused)
        self.assertIn("ACTION: rerun", refused)
        self.assertIn("session-done ran with no session phase pending.", refused)
        self.assertIn(f"COMMAND: {self.own_command('resume')}", refused)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_run_notes_on_a_session_phase_reach_the_session_brief(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2", "only", "touch", "totals")

        self.assertIn("Run notes from the user.", out)
        self.assertIn("only touch totals", out)

    def test_session_done_for_another_phase_is_refused_and_leaves_the_open_session_phase_unchecked(self):
        session_phase = SESSION_PHASE_TEXT
        old_phase = "## Phase 2: Totals\n\n**File**: `backend/src/totals.ts`\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(old_phase, session_phase))
        self.finish_phase_one()
        self.step("start", self.plan, "--phase", "2")

        refused = self.step("session-done", "3")

        self.assertIn("session-done takes the open phase's id", refused)
        self.assertIn("session-done 2", refused)
        self.assertIn("- [ ] Phase 2:", self.plan_text())
        self.assertEqual(self.state()["stage"], "session")

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

    def test_a_refusal_over_a_run_of_another_session_does_not_offer_restart(self):
        self.coder_round()
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-2"

        out = self.step("start", "--task", "fix the typo")

        self.assertTrue(out.startswith("Refused: "), out)
        self.assertNotIn("code_step.py start --restart", out)
        self.assertNotIn("ACTION: rerun", out)
        self.assertIn("ACTION: stop", out)
        self.assertIn("The task was not started.", out)
        self.assertIn("another session", out)
        self.assertIn("--repo", out)

    def stop_a_reviewed_phase_on_a_counted_check(self):
        # The first phase's code is reviewed and stopped on its one Automated Verification check, which fails while
        # orders.ts holds console.log and adds a line to .git/av-runs each time it runs.
        counted_check = ("import pathlib; open('.git/av-runs', 'a').write('run\\n'); "
                         "raise SystemExit('console.log' in pathlib.Path('backend/src/orders.ts').read_text())")
        self.set_verification(f'- [ ] **Prohibition**: no console.log - `python3 -c "{counted_check}"`')
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("resume"))

    def check_runs(self):
        return (self.repo / ".git/av-runs").read_text().count("run\n")

    def test_a_restart_over_a_reviewed_phase_whose_checks_pass_closes_it_without_a_coder(self):
        self.stop_a_reviewed_phase_on_a_counted_check()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")

        out = self.step("start", "--restart")

        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())
        self.assertEqual(2, self.check_runs())

    def test_a_restart_over_a_reviewed_phase_whose_checks_fail_dispatches_a_coder(self):
        self.stop_a_reviewed_phase_on_a_counted_check()

        out = self.step("start", "--restart")

        self.assertIn("AGENT: coder", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    # ---------- an open run whose phase may close ----------

    def test_start_over_a_run_that_verify_may_close_offers_verify_first(self):
        self.stop_a_reviewed_phase_on_a_counted_check()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")

        refused = self.step("start", "--task", "the next phase")
        out = self.step(*self.args_of_printed_command(refused, "verify"))

        self.assertIn("Run `verify` first", refused)
        self.assertIn("Phase 1 marked done", out)

    def test_start_with_no_arguments_over_a_run_that_verify_may_close_reruns_verify(self):
        self.stop_a_reviewed_phase_on_a_counted_check()

        out = self.step("start")

        self.assertIn("ACTION: rerun", out)
        self.assertIn("code_step.py verify", out)

    # ---------- --task wins ----------

    def test_task_flag_always_starts_a_planless_run_however_the_arguments_arrive(self):
        self.finish_phase_one()
        saved_state = (self.repo / ".git/code-step/state.json").read_bytes()
        cases = [
            ("two arguments", ["--task", "fix the typo"]),
            ("one quoted argument", ['--task "fix the typo"']),
            ("one argument with a modifier", ['+deep --task "fix the typo"']),
            ("one argument with a phase flag in the text", ['--task "fix the typo" --phase 2']),
            ("after a plan", [self.plan, "--task", "fix the typo"]),
        ]

        for label, start_args in cases:
            with self.subTest(label):
                (self.repo / ".git/code-step/state.json").write_bytes(saved_state)

                out = self.step("start", *start_args)

                self.assertIn("AGENT: coder", out)
                self.assertIn("Implement: fix the typo", out)
                self.assertIsNone(self.state().get("plan"))

    # ---------- --phase with run notes and no plan ----------

    def test_phase_and_notes_with_no_plan_path_pass_the_notes_to_the_coder_using_the_saved_plan(self):
        self.finish_phase_one()

        out = self.step("start", "--phase", "2", "only", "touch", "totals")

        self.assertIn("AGENT: coder", out)
        self.assertIn("Run notes from the user.", out)
        self.assertIn("only touch totals", out)
        self.assertEqual("2", self.state()["phase"])
        self.assertEqual(self.plan, self.state()["plan"])

    # ---------- --repo ----------

    def other_repo(self):
        other = self.tmp / "other"
        shutil.copytree(self.repo, other, symlinks=True)
        return other

    def test_repo_flag_opens_the_run_in_that_checkout_and_ignores_an_open_run_of_the_cwd_repo(self):
        other = self.other_repo()
        self.coder_round()

        out = self.step("start", "--repo", str(other), "--task", "fix the typo")

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"This run's checkout is {other}", out)
        self.assertTrue((other / ".git/code-step/state.json").exists())
        self.assertEqual("review", self.state()["stage"])

    def test_a_repo_line_at_the_top_of_the_task_file_picks_the_checkout(self):
        other = self.other_repo()
        self.coder_round()
        for label, header in (("Repo", f"Repo: {other}"), ("Repo root", f"Repo root: {other}")):
            with self.subTest(label):
                (other / ".git/code-step/state.json").unlink(missing_ok=True)
                task_file = self.write_outside_file("brief.md", f"{header}\nAdd retries to the orders client.\n")

                out = self.step("start", "--task-file", str(task_file))

                self.assertIn("AGENT: coder", out)
                self.assertIn(f"This run's checkout is {other}", out)
                self.assertTrue((other / ".git/code-step/state.json").exists())

    def test_a_relative_task_file_path_still_reads_the_file_when_start_moves_to_another_checkout(self):
        other = self.other_repo()
        (self.repo / "brief.md").write_text(f"Repo: {other}\nAdd retries to the orders client.\n")

        out = self.step("start", "--task-file", "brief.md")

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"This run's checkout is {other}", out)
        self.assertIn("Add retries to the orders client.", out)

    def test_a_relative_task_file_path_is_read_from_the_original_directory_with_a_repo_flag(self):
        other = self.other_repo()
        (self.repo / "brief.md").write_text("Add retries to the orders client.\n")

        out = self.step("start", "--repo", str(other), "--task-file", "brief.md")

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"This run's checkout is {other}", out)
        self.assertIn("Implement: Add retries to the orders client.", out)

    def test_repo_flag_without_a_path_or_before_another_flag_is_a_usage_error(self):
        for args in (["--repo"], ["--repo", "--task", "x"]):
            with self.subTest(args=args):
                finished = base.run(self.repo, self.env, "start", *args)

                self.assertEqual(2, finished.returncode)
                self.assertIn("--repo needs a path", finished.stderr)

    def test_refusals_over_an_open_run_keep_the_repo_flag_in_the_commands_they_print(self):
        other = self.other_repo()
        self.step("start", "--repo", str(other), "--task", "first job")

        finished = base.run(self.repo, self.env, "start", "--repo", str(other), "fix", "the", "typo")
        out = finished.stdout

        self.assertTrue(out.startswith("Refused: "), finished.stderr)
        self.assertIn(f"start --repo {other} --restart", out)

    def assert_printed_start_commands_keep_the_repo_flag(self, out, other):
        start_commands = [line for line in out.splitlines() if "code_step.py start" in line]
        self.assertTrue(start_commands, out)
        for command in start_commands:
            self.assertIn(f"--repo {other}", command)

    def test_refusals_keep_the_repo_flag_for_a_verb_a_ticket_id_and_a_phase_flag_in_task_text(self):
        other = self.other_repo()
        cases = {
            "verb as task text": ["resume", "now"],
            "text after a ticket id": ["PROJ-12", "is", "broken"],
            "phase flag inside task text": ["fix", "the", "typo", "--phase", "2"],
        }
        for name, words in cases.items():
            with self.subTest(case=name):
                finished = base.run(self.repo, self.env, "start", "--repo", str(other), *words)

                self.assertTrue(finished.stdout.startswith("Refused: "), finished.stdout + finished.stderr)
                self.assert_printed_start_commands_keep_the_repo_flag(finished.stdout, other)

    def test_a_refusal_of_a_non_plan_file_outside_the_repo_keeps_the_repo_flag(self):
        other = self.other_repo()
        brief = self.write_outside_file("brief.md", "Add retries to the orders client.\n")

        finished = base.run(self.repo, self.env, "start", "--repo", str(other), str(brief))

        self.assertTrue(finished.stdout.startswith("Refused: "), finished.stdout + finished.stderr)
        self.assert_printed_start_commands_keep_the_repo_flag(finished.stdout, other)

    def test_a_refusal_of_task_text_over_a_plan_with_open_phases_keeps_the_repo_flag(self):
        self.finish_phase_one()
        other = self.other_repo()

        finished = base.run(self.repo, self.env, "start", "--repo", str(other), "fix", "the", "typo")

        self.assertIn("has open phases", finished.stdout, finished.stderr)
        self.assert_printed_start_commands_keep_the_repo_flag(finished.stdout, other)

    def test_a_repo_word_inside_task_text_is_not_the_repo_flag(self):
        finished = base.run(self.repo, self.env, "start", "add", "a", "--repo", "flag", "to", "the", "cli")

        self.assertIn("AGENT: coder", finished.stdout, finished.stderr)
        self.assertIn("add a --repo flag to the cli", finished.stdout)

    def test_a_task_file_word_inside_task_text_leaves_the_text_as_typed(self):
        finished = base.run(self.repo, self.env, "start", "document", "the", "--task-file", "option")

        self.assertIn("AGENT: coder", finished.stdout, finished.stderr)
        self.assertIn("document the --task-file option", finished.stdout)

    def test_repo_flag_outside_a_git_repo_exits_non_zero_and_changes_nothing(self):
        outside = self.tmp / "scratchpad"
        outside.mkdir()

        finished = base.run(self.repo, self.env, "start", "--repo", str(outside), "--task", "x")

        self.assertNotEqual(0, finished.returncode)
        self.assertIn("not inside a git repo", finished.stderr)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

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


class GateEvidenceTest(base.CodeStepTest):
    GATED_TITLE = "- [ ] Phase 2: Totals (risk: low)"
    GATE_EVIDENCE = 'outside session, 2026-10-30 09:15: "release phase 2"'

    def gate_phase_two(self):
        plan_path = self.repo / self.plan
        gated_text = plan_path.read_text().replace(
            self.GATED_TITLE, "- [ ] Phase 2: Totals — gate: an outside session sends release (risk: low)")
        plan_path.write_text(gated_text)
        self.finish_phase_one()

    def test_a_gated_phase_started_with_gate_evidence_puts_the_evidence_in_the_coder_packet(self):
        self.gate_phase_two()

        out = self.step("start", self.plan, "--phase", "2", "--gate-evidence", self.GATE_EVIDENCE)

        self.assertIn("AGENT: coder", out)
        self.assertIn("an outside session sends release", out)
        self.assertIn(self.GATE_EVIDENCE, out)
        self.assertIn("The caller released this gate with the evidence above", out)

    def test_gate_evidence_on_a_phase_with_no_gate_is_refused(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "2", "--gate-evidence", self.GATE_EVIDENCE)

        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Phase 2 has no gate clause", out)

    def test_gate_evidence_without_a_phase_is_refused(self):
        self.gate_phase_two()

        out = self.step("start", self.plan, "--gate-evidence", self.GATE_EVIDENCE)

        self.assertNotIn("AGENT: coder", out)
        self.assertIn("--gate-evidence needs --phase", out)

    def test_gate_evidence_on_task_text_is_refused(self):
        out = self.step("start", "--gate-evidence", self.GATE_EVIDENCE, "--task", "fix the typo")

        self.assertNotIn("AGENT: coder", out)
        self.assertIn("--gate-evidence needs --phase", out)

    def test_gate_evidence_on_a_phase_with_task_text_is_refused(self):
        self.gate_phase_two()

        out = self.step("start", "--phase", "2", "--gate-evidence", self.GATE_EVIDENCE, "--task", "fix")

        self.assertNotIn("AGENT: coder", out)
        self.assertIn("a --task run has no plan", out)

    def test_gate_evidence_on_a_closing_phase_is_refused(self):
        plan_path = self.repo / self.plan
        closing_title = "- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)"
        gated_text = plan_path.read_text().replace(
            closing_title, closing_title.replace("(risk", "— gate: an outside session sends release (risk"))
        plan_path.write_text(gated_text)
        self.finish_phase_one()

        out = self.step("start", self.plan, "--phase", "4", "--gate-evidence", self.GATE_EVIDENCE)

        self.assertNotIn("ACTION: invoke-skill", out)
        self.assertIn("closing phase", out)

    def test_the_gate_stop_for_a_gated_closing_phase_names_no_evidence_command(self):
        plan_path = self.repo / self.plan
        closing_title = "- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)"
        gated_text = plan_path.read_text().replace(
            closing_title, closing_title.replace("(risk", "— gate: an outside session sends release (risk"))
        gated_text = gated_text.replace(self.GATED_TITLE, self.GATED_TITLE.replace("[ ]", "[x]"))
        gated_text = gated_text.replace("- [ ] Phase 3: Audit trail", "- [x] Phase 3: Audit trail")
        plan_path.write_text(gated_text)
        self.finish_phase_one()

        out = self.step("start", self.plan)

        self.assertIn("gate", out)
        self.assertIn("Tell the user.", out)
        self.assertNotIn("--gate-evidence", out)

    def test_the_gate_stop_names_the_one_step_command_for_the_first_gated_phase(self):
        self.gate_phase_two()

        out = self.step("start", self.plan)

        self.assertIn("start --phase 2 --gate-evidence", out)
        self.assertIn("released the gate in their own words", out)
        self.assertNotIn("second confirmation", out)

    def test_the_placeholder_text_is_refused_as_gate_evidence(self):
        self.gate_phase_two()

        finished = base.run(self.repo, self.env, "start", self.plan, "--phase", "2", "--gate-evidence",
                            "<who>, <when>: <quoted text>")

        self.assertEqual(2, finished.returncode)
        self.assertIn("--gate-evidence needs the evidence text", finished.stderr)


class StartArgsTest(unittest.TestCase):
    """The phase id, plan and run notes that the start arguments read as, before any run state is touched."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.plan = str(pathlib.Path(temp_dir.name) / "spec.md")
        pathlib.Path(self.plan).write_text("## Phase 1: First\n")

    def parse(self, args, saved_plan=None):
        args = code_step_start_args.split_quoted_flags(args)
        args = code_step_start.phase_words_as_flag(args)
        parsed = code_step_start.parse_start_args(args)
        return code_step_start_args.carry_run_notes(parsed, saved_plan)

    def test_the_phase_id_the_plan_and_the_run_notes_are_read_from_the_arguments(self):
        plan = self.plan
        cases = [
            ("plan then --phase then notes", [plan, "--phase", "2", "only", "touch", "totals; no console.log"],
             None, [plan], "2", "only touch totals; no console.log", False),
            ("plan then the words Phase and an id then notes", [plan, "Phase", "2", "only", "touch", "totals"],
             None, [plan], "2", "only touch totals", False),
            ("plan then the words Phase and an id", [plan, "Phase", "2"], None, [plan], "2", None, False),
            ("plan and a bare id in one quoted argument", [f"{plan} 2"], None, [plan], "2", None, False),
            ("--phase and notes with no plan takes the saved plan", ["--phase", "2", "only", "touch", "totals"],
             plan, [plan], "2", "only touch totals", False),
            ("--restart then --phase then notes", ["--restart", "--phase", "2", "split", "it", "by", "file"],
             plan, [plan], "2", "split it by file", True),
            ("--phase then --restart then notes", ["--phase", "1", "--restart", "keep", "it", "short"],
             plan, [plan], "1", "keep it short", True),
            ("flags, phase id and notes in one quoted argument", ["--restart --phase 2 split it by file"],
             plan, [plan], "2", "split it by file", True),
        ]
        for label, args, saved_plan, plan_args, phase_id, run_notes, restart in cases:
            with self.subTest(label):
                parsed = self.parse(args, saved_plan)

                self.assertEqual(plan_args, parsed.plan_args)
                self.assertEqual(phase_id, parsed.phase_id)
                self.assertEqual(run_notes, parsed.run_notes)
                self.assertEqual(restart, parsed.restart)
                self.assertIsNone(parsed.task_text)

    def test_each_switch_and_task_file_in_one_quoted_argument_splits_into_its_words(self):
        cases = [
            ("--headless first", ["--headless --task fix the totals"], "headless"),
            ("--coder-stopped first", ["--coder-stopped --task fix the totals"], "coder_stopped"),
            ("--restart first", ["--restart --task fix the totals"], "restart"),
        ]
        for label, args, switch in cases:
            with self.subTest(label):
                parsed = self.parse(args)

                self.assertEqual("fix the totals", parsed.task_text)
                self.assertTrue(getattr(parsed, switch))

        task_file = pathlib.Path(self.plan).parent / "task.txt"
        task_file.write_text("fix the totals\n")

        parsed = self.parse([f"--task-file {task_file}"])

        self.assertEqual("fix the totals\n", parsed.task_text)


def load_tests(loader, tests, pattern):
    # The tests of CodeStepTest run in test_code_step.py: this file runs its own.
    own_tests = unittest.TestSuite()
    for case_class in (StartInputTest, GateEvidenceTest):
        own_names = [name for name in loader.getTestCaseNames(case_class) if name in case_class.__dict__]
        own_tests.addTests(case_class(name) for name in own_names)
    own_tests.addTests(loader.loadTestsFromTestCase(StartArgsTest))
    return own_tests


if __name__ == "__main__":
    unittest.main()
