"""The `resume` verb of code_step.py, the refusals of `start` and of the guarded verbs, and the match of a
review-loop hand-back to the review it was launched for.

Each test gives a saved state, runs one verb and checks what the main session is told and what the saved state
became. The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_resume
"""
import fcntl
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import test_code_step as base

SETUP_FAULT_PACKET = "status: setup-fault\niter: 1\nblockers:\n  - finding: no package.json\n    file_line: none"
BLOCKER_PACKET = "status: critical-blocker\niter: 1\nblockers:\n  - finding: b\n    file_line: backend/src/orders.ts:1"
UNVERIFIED_PACKET = ("status: converged\niter: 1\nfixed: []\nask: []\nnit: []\n"
                     "full_check: unverified (exit 0, no runner summary)\nfull_check_command: npm run lint")


class ResumeTest(base.CodeStepTest):
    def state_bytes(self):
        return (self.repo / ".git/code-step/state.json").read_bytes()

    def assert_refused_with_rerun(self, out, verb_words):
        self.assertTrue(out.startswith("Refused: "), out)
        self.assertIn("ACTION: rerun", out)
        self.assertIn(f"COMMAND: {self.own_command(verb_words)}", out)

    def assert_refused_with_choices(self, out, *command_words):
        self.assertTrue(out.startswith("Refused: "), out)
        self.assertIn("ACTION: stop", out)
        for words in command_words:
            self.assertIn(self.own_command(words), out)

    def stop_the_coder_at_the_wait_cap(self, launched_as=None):
        self.start_phase_one()
        if launched_as:
            dispatch_id = self.events_named("dispatch")[-1]["id"]
            self.launch_agent(f"code-step-dispatch: {self.state()['runId']}/{dispatch_id}", agent_id=launched_as)
            self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")
        out = self.step("resume")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        return out

    # ---------- start refuses what resume or --task is for ----------

    def test_start_with_the_name_of_a_replaced_verb_is_refused_and_changes_nothing(self):
        self.coder_round()
        before = self.state_bytes()

        for replaced_verb in ("after-review", "after-plan-edit"):
            out = self.step("start", replaced_verb)

            self.assert_refused_with_rerun(out, "resume")
            self.assertEqual(before, self.state_bytes())
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Phase 1 marked done", self.step("resume"))

    def test_start_continue_after_a_finished_phase_is_refused_and_resume_dispatches_the_next_phase(self):
        self.finish_phase_one()
        before = self.state_bytes()

        out = self.step("start", "continue")

        self.assert_refused_with_rerun(out, "resume")
        self.assertEqual(before, self.state_bytes())
        resumed = self.step("resume")
        self.assertIn("AGENT: coder", resumed)
        self.assertIn("Phase 2", resumed)
        self.assertEqual(self.plan, self.state()["plan"])

    def test_start_with_a_plan_and_a_phase_before_text_takes_the_text_as_run_notes(self):
        self.finish_phase_one()

        spread = self.step("start", self.plan, "--phase", "2", "—", "add", "the", "brief")
        self.assertIn("— add the brief", spread)
        self.assertEqual("2", self.state()["phase"])
        quoted = self.step("start", "--restart", f"{self.plan} --phase 2 — add the brief")

        self.assertIn("AGENT: coder", spread)
        self.assertIn("— add the brief", quoted)

    def test_start_restart_with_a_phase_id_then_run_notes_over_a_stopped_phase_keeps_the_notes(self):
        self.begin_coder()
        self.set_state(stage="stopped", stopReason="coder-cap")

        out = self.step("start", "--restart", "--phase", "1", "work", "on", "the", "first", "part")

        self.assertIn("ACTION: dispatch", out)
        self.assertIn("work on the first part", out)

    def test_start_with_a_phase_and_no_plan_and_no_saved_plan_before_task_text_is_refused_with_the_two_commands(self):
        out = self.step("start", "--phase", "2", "—", "brief")

        self.assert_refused_with_choices(out, "start --phase 2", "start --task '— brief'")
        self.assertIn("was not passed to the coder", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_start_with_a_replaced_verb_followed_by_words_is_refused_with_resume_and_the_task_command(self):
        self.finish_phase_one()
        before = self.state_bytes()

        out = self.step("start", "continue", "the", "login", "fix")

        self.assert_refused_with_choices(out, "resume", "start --task 'continue the login fix'")
        self.assertEqual(before, self.state_bytes())

    def test_start_with_blank_task_text_and_no_open_run_starts_the_plan_like_a_bare_start(self):
        other_repo = self.tmp / "other"
        shutil.copytree(self.repo, other_repo, symlinks=True)

        blank = self.step("start", "  ")
        bare = base.run(other_repo, self.env, "start").stdout

        self.assertEqual(bare.replace(str(other_repo), str(self.repo)), blank)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_start_with_blank_task_text_over_an_open_run_is_refused_with_resume_like_a_bare_start(self):
        self.coder_round()
        before = self.state_bytes()

        for blank_args in (("  ",), ("--task", "  "), ("--task",)):
            with self.subTest(blank_args=blank_args):
                out = self.step("start", *blank_args)

                self.assert_refused_with_rerun(out, "resume")
                self.assertEqual(before, self.state_bytes())

    def test_start_with_a_directory_or_a_ticket_id_before_words_offers_the_start_and_a_task_of_all_the_words(self):
        self.finish_phase_one()
        before = self.state_bytes()
        cases = [(["backend", "needs", "a", "retry"], "start backend", "backend needs a retry"),
                 (["PROJ-12", "is", "broken"], "start PROJ-12", "PROJ-12 is broken"),
                 (["--phase", "2", "backend", "needs", "a", "retry"], "start backend --phase 2",
                  "backend needs a retry")]

        for start_args, start_command, task_text in cases:
            with self.subTest(start_args=start_args):
                out = self.step("start", *start_args)

                self.assert_refused_with_choices(out, start_command, f"start --task '{task_text}'")
                self.assertIn("was not passed to the coder", out)
                self.assertEqual(before, self.state_bytes())

    def test_start_with_a_directory_before_words_in_one_quoted_argument_is_task_text(self):
        self.finish_phase_one()
        before = self.state_bytes()

        out = self.step("start", "backend needs a retry")

        self.assert_refused_with_choices(out, "resume", "start --task 'backend needs a retry'")
        self.assertNotIn("was not passed to the coder", out)
        self.assertEqual(before, self.state_bytes())

    def test_start_with_a_directory_before_words_and_no_saved_plan_dispatches_no_coder_unless_quoted(self):
        refused = self.step("start", "backend", "needs", "a", "retry")

        self.assertIn("ACTION: stop", refused)
        self.assertNotIn("AGENT: coder", refused)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())
        quoted = self.step("start", "backend needs a retry")
        self.assertIn("Implement: backend needs a retry", quoted)
        self.assertIsNone(self.state()["plan"])

    def test_start_with_a_phase_flag_in_the_text_that_has_no_phase_id_after_it_stays_task_text(self):
        self.finish_phase_one()
        before = self.state_bytes()

        for task_words in (["document", "the", "--phase", "flag"], ["document", "the", "--phase"]):
            with self.subTest(task_words=task_words):
                out = self.step("start", *task_words)

                self.assert_refused_with_choices(out, "resume", f"start --task '{' '.join(task_words)}'")
                self.assertNotIn("was not passed to the coder", out)
                self.assertEqual(before, self.state_bytes())

    def test_start_start_and_start_status_over_an_open_run_rerun_the_verb_after_start(self):
        self.coder_round()
        before = self.state_bytes()

        restarted = self.step("start", "start", "--restart")
        statused = self.step("start", "status")

        self.assert_refused_with_rerun(restarted, "start --restart")
        self.assert_refused_with_rerun(statused, "status")
        self.assertEqual(before, self.state_bytes())

    def test_start_status_and_start_start_followed_by_plain_words_are_task_text(self):
        for task_words in (["status", "page", "shows", "wrong", "count"], ["start", "caching", "the", "list"]):
            with self.subTest(task_words=task_words):
                out = self.step("start", "--restart", *task_words)

                self.assertIn(f"Implement: {' '.join(task_words)}", out)
                self.assertIsNone(self.state()["plan"])

    def test_both_task_choices_keep_the_users_modifier(self):
        self.finish_phase_one()

        over_plan = self.step("start", "+deep", "fix", "the", "typo")
        over_directory = self.step("start", "+deep", "backend", "needs", "a", "retry")

        self.assert_refused_with_choices(over_plan, "resume", "start +deep --task 'fix the typo'")
        self.assert_refused_with_choices(over_directory, "start backend +deep",
                                         "start +deep --task 'backend needs a retry'")

    def test_a_source_file_before_words_is_kept_in_the_task_choice(self):
        self.finish_phase_one()
        self.assertTrue((self.repo / "backend/src/orders.ts").is_file())

        out = self.step("start", "backend/src/orders.ts", "throws", "on", "empty", "cart")

        self.assert_refused_with_choices(out, "start backend/src/orders.ts",
                                         "start --task 'backend/src/orders.ts throws on empty cart'")

    def restart_text_after_a_stop(self, *start_options):
        self.coder_round(start_options=start_options)
        self.hook("review-loop", BLOCKER_PACKET)
        self.step("resume")
        self.step("resume")
        return self.said()

    def test_the_restart_text_names_the_modifier_and_the_phase_the_run_started_with(self):
        runs = [
            ("deep run", ("+deep",), "run `start --restart +deep`", "--phase"),
            ("single phase run", ("--phase", "1"), "run `start --restart --phase 1`", "+fast"),
            ("single phase fast run", ("--phase", "1", "+fast"), "run `start --restart --phase 1 +fast`", "+deep"),
        ]
        for label, start_options, restart_command, left_out in runs:
            with self.subTest(label):
                self.setUp()
                said = self.restart_text_after_a_stop(*start_options)

                self.assertIn(restart_command, said)
                self.assertNotIn(left_out, said)

    def test_start_with_task_text_over_a_plan_with_open_phases_names_resume_and_task(self):
        self.finish_phase_one()

        out = self.step("start", "fix", "the", "typo")

        self.assert_refused_with_choices(out, "resume", "start --task 'fix the typo'")
        planless = self.step("start", "--task", "fix", "the", "typo")
        self.assertIn("AGENT: coder", planless)
        self.assertIsNone(self.state().get("plan"))

    def test_start_with_a_task_over_an_unfinished_run_is_refused_and_keeps_the_asks(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("resume")
        self.assertEqual("asks", self.state()["stage"])
        before = self.state_bytes()

        out = self.step("start", "--task", "x")

        self.assert_refused_with_choices(out, "resume", "start --restart --task x")
        self.assertEqual(before, self.state_bytes())

    def test_start_over_an_unfinished_run_with_no_arguments_is_refused_with_resume(self):
        self.coder_round()
        before = self.state_bytes()

        out = self.step("start")

        self.assert_refused_with_rerun(out, "resume")
        self.assertEqual(before, self.state_bytes())

    def test_start_with_a_verb_name_that_carries_input_is_refused_with_that_verb_and_names_task(self):
        out = self.step("start", "verify", "the", "login")

        self.assert_refused_with_rerun(out, "verify the login")
        self.assertIn("start --task 'verify the login'", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    def test_a_guarded_verb_with_nothing_pending_is_refused_with_resume(self):
        no_state = self.step("asks-done", "accepted")
        self.assert_refused_with_rerun(no_state, "resume")

        self.coder_round()
        before = self.state_bytes()
        at_review = self.step("asks-done", "accepted")

        self.assert_refused_with_rerun(at_review, "resume")
        self.assertEqual(before, self.state_bytes())

    def test_resume_with_an_argument_is_refused_and_names_task(self):
        self.start_phase_one()
        before = self.state_bytes()

        out = self.step("resume", "x")

        self.assert_refused_with_rerun(out, "resume")
        self.assertIn("start --task", out)
        self.assertEqual(before, self.state_bytes())

    def test_resume_with_text_that_names_a_task_file_and_no_open_run_starts_a_run_with_it(self):
        task_file = self.tmp / "scratchpad" / "brief.md"
        task_file.parent.mkdir()
        task_file.write_text("Add retries to the orders client.\n")
        task_text = f"Task file: {task_file}. Repo: {self.repo}"

        out = self.step("resume", task_text)

        self.assertIn("AGENT: coder", out)
        self.assertIn(f"Implement: {task_text}", out)
        self.assertIsNone(self.state().get("plan"))

    def test_resume_with_a_task_file_path_and_no_open_run_prints_the_task_file_start(self):
        task_file = self.tmp / "scratchpad" / "brief.md"
        task_file.parent.mkdir()
        task_file.write_text("Add retries to the orders client.\n")

        out = self.step("resume", str(task_file))

        self.assert_refused_with_rerun(out, f"start --task-file {task_file}")
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    # ---------- a new session takes the run over ----------

    NEW_SESSION = "sess-2"

    def test_a_resume_from_a_new_session_keeps_the_open_asks_and_takes_their_answers(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("resume")
        self.env["CLAUDE_CODE_SESSION_ID"] = self.NEW_SESSION

        resumed = self.step("resume")
        stage_after_resume = self.state()["stage"]
        answered = self.step("asks-done", "rejected")

        self.assertIn("ACTION: ask-user", resumed)
        self.assertEqual("asks", stage_after_resume)
        self.assert_first_phase_ticked()
        self.assert_marked_clean(answered, self.NEW_SESSION)

    def test_a_review_again_from_a_new_session_pins_the_run_to_it_so_its_hand_back_counts(self):
        self.stop_the_review_at_the_wait_cap()
        self.env["CLAUDE_CODE_SESSION_ID"] = self.NEW_SESSION

        self.step("review-again")
        pinned_session = self.state()["sessionId"]
        self.hook("review-loop", self.LOOP_OK, agent_id="r2", session=self.NEW_SESSION)
        self.step("resume")

        self.assertEqual(self.NEW_SESSION, pinned_session)
        self.assert_first_phase_ticked()

    # ---------- one verb at a time on a run ----------

    def hold_the_verb_lock(self):
        lock_file = self.enterContext(open(self.repo / ".git/code-step/verb.lock", "a+"))
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file

    def test_a_resume_while_another_verb_runs_on_the_run_stops_and_changes_nothing(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        before = self.state_bytes()
        lock_file = self.hold_the_verb_lock()

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn("another code_step verb is running on this run", out)
        self.assertEqual(before, self.state_bytes())
        lock_file.close()
        self.assertIn("Phase 1 marked done", self.step("resume"))

    def test_an_abort_runs_while_another_verb_holds_the_run(self):
        self.coder_round()
        self.hold_the_verb_lock()

        out = self.step("abort")

        self.assertNotIn("another code_step verb is running", out)
        self.assertFalse((self.repo / ".git/code-step/state.json").exists())

    # ---------- resume by saved state ----------

    def test_resume_with_no_saved_run_does_what_a_bare_start_does(self):
        other_repo = self.tmp / "other"
        shutil.copytree(self.repo, other_repo, symlinks=True)

        resumed = self.step("resume")
        started = base.run(other_repo, self.env, "start").stdout

        self.assertEqual(started.replace(str(other_repo), str(self.repo)), resumed)

    def test_resume_after_a_clean_review_marks_the_phase_done(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("resume")

        self.assertIn("Phase 1 marked done", out)

    def test_resume_twice_at_the_asks_prints_the_same_ask_and_leaves_the_saved_state_alone(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("resume")
        first = self.step("resume")
        state_after_first = self.state_bytes()

        second = self.step("resume")

        self.assertIn("ACTION: ask-user", first)
        self.assertIn("keep?", self.said())
        self.assertEqual(first, second)
        self.assertEqual(state_after_first, self.state_bytes())

    def test_resume_at_a_plan_impact_asks_for_the_ruling_again(self):
        self.coder_round(self.IMPACT_REPORT)
        before = self.state_bytes()

        first = self.step("resume")
        second = self.step("resume")

        self.assertIn("ACTION: ask-user", first)
        self.assertIn("decide", self.said())
        self.assertEqual(first, second)
        self.assertEqual(before, self.state_bytes())

    def test_resume_at_the_plan_edit_waits_for_the_plan_coder_and_then_dispatches_the_review(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("resume"))

        self.hook("coder", "BEHAVIOR: plan rewritten", agent_id="plan-edit")

        self.assertIn("AGENT: review-loop", self.step("resume"))

    # ---------- the stops resume leaves ----------

    def test_resume_at_a_stop_with_no_recorded_reason_asks_for_status_or_a_restart(self):
        self.coder_round()
        self.hook("review-loop", BLOCKER_PACKET)
        self.step("resume")
        self.set_state(stop=None)
        self.assertEqual("stopped", self.state()["stage"])
        before = self.state_bytes()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"`{self.own_command('status')}`", self.said())
        self.assertIn("start --restart", self.said())
        self.assertEqual(before, self.state_bytes())

    def test_resume_and_review_again_at_a_critical_blocker_stop_do_not_point_at_each_other(self):
        self.coder_round()
        self.hook("review-loop", BLOCKER_PACKET)
        self.step("resume")
        self.assertEqual(("stopped", "critical-blocker"), (self.state()["stage"], self.state()["stop"]["kind"]))
        review_again = self.own_command("review-again")

        resume_out = self.step("resume")

        self.assertIn("ACTION: ask-user", resume_out)
        self.assertIn(f"`{review_again}`", self.said())
        self.assertNotIn("Refused", resume_out)

        review_again_out = self.step("review-again")

        self.assertNotIn("Refused", review_again_out)
        self.assertIn("AGENT: review-loop", review_again_out)

    def test_resume_at_a_stop_for_a_guarded_verb_prints_the_state_and_names_that_verb(self):
        self.leave_unreadable_packet()
        self.step("resume")
        self.assertEqual("invalid-packet", self.state()["stop"]["kind"])

        self.step("resume")

        self.assertIn("stage stopped with stop reason invalid-packet", self.said())
        self.assertIn("`review-again`", self.said())
        self.assertNotIn("start --restart", self.said())

    def test_resume_at_a_failed_verification_stop_names_verify(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("resume"))
        self.assertEqual("verification", self.state()["stop"]["kind"])

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("stage stopped with stop reason verification", self.said())
        self.assertIn("`verify`", self.said())

    def launch_hook_result(self, skill, args, cwd=None):
        cwd = cwd or self.repo
        event = {"cwd": str(cwd), "session_id": self.SESSION, "tool_name": "Skill",
                 "tool_input": {"skill": skill, "args": args}}
        return base.run(cwd, self.env, "launch-hook", stdin=json.dumps(event))

    def assert_launch_hook_passes(self, skill, args, cwd=None):
        result = self.launch_hook_result(skill, args, cwd)

        self.assertEqual("", result.stdout)
        self.assertEqual("", result.stderr)

    def launch_hook_decision(self, skill, args, cwd=None):
        stdout = self.launch_hook_result(skill, args, cwd).stdout

        return json.loads(stdout)["hookSpecificOutput"]

    def stop_at_verification(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.step("resume")
        self.assertEqual("verification", self.state()["stop"]["kind"])

    def test_a_resume_at_a_failed_verification_stop_is_refused_before_the_fork_starts_and_names_fix_then_verify(self):
        self.stop_at_verification()

        for args in ("", "resume", "continue", "after-plan-edit", "resume x"):
            with self.subTest(args=args):
                decision = self.launch_hook_decision("code", args)

                self.assertEqual("deny", decision["permissionDecision"])
                self.assertIn("Dispatch the fix", decision["permissionDecisionReason"])
                self.assertIn("invoke Skill code with `verify`", decision["permissionDecisionReason"])
        self.assert_launch_hook_passes("code", "verify")
        self.assert_launch_hook_passes("review", "")

    def test_missing_plan_at_verify_stops(self):
        self.stop_at_verification()
        (self.repo / self.plan).unlink()

        out = self.step("verify")

        self.assertIn("ACTION: stop", out)
        self.assertIn("is missing (a branch switch", out)

    def test_a_resume_at_an_unparsed_verification_item_stop_is_refused_and_names_a_plan_edit(self):
        self.coder_round_then_edit_verification("- [ ] **Check**: the streams pass, see the log")
        self.hook("review-loop", self.LOOP_OK)
        self.step("resume")
        self.assertEqual("verification", self.state()["stop"]["kind"])

        decision = self.launch_hook_decision("code", "resume")

        self.assertEqual("deny", decision["permissionDecision"])
        self.assertIn("an item could not be run", decision["permissionDecisionReason"])
        self.assertIn("edit the plan for an item that could not be run", decision["permissionDecisionReason"])
        self.assertIn("invoke Skill code with `verify`", decision["permissionDecisionReason"])

    def test_the_launch_hook_checks_only_the_resumed_run_when_a_pinned_checkout_is_stopped_at_verification(self):
        self.start_phase_one()
        healthy_repo = self.tmp / "healthy"
        shutil.copytree(self.repo, healthy_repo, symlinks=True)
        self.stop_at_verification()

        self.assert_launch_hook_passes("code", "resume", healthy_repo)

    def test_the_launch_hook_follows_the_sessions_only_open_run_when_the_cwd_holds_no_run(self):
        cwd = self.tmp / "cwd"
        shutil.copytree(self.base_repo, cwd, symlinks=True)
        self.start_phase_one()
        self.stop_at_verification()

        decision = self.launch_hook_decision("code", "resume", cwd)

        self.assertEqual("deny", decision["permissionDecision"])
        self.assertIn(str(self.repo.resolve()), decision["permissionDecisionReason"])

    def test_the_launch_hook_lets_a_resume_through_when_two_open_runs_lie_outside_the_cwd(self):
        self.start_phase_one()
        self.stop_at_verification()
        second_run = self.tmp / "second"
        shutil.copytree(self.base_repo, second_run, symlinks=True)
        base.run(second_run, self.env, "start", "--task", "add retries")
        cwd = self.tmp / "cwd"
        shutil.copytree(self.base_repo, cwd, symlinks=True)

        self.assert_launch_hook_passes("code", "resume", cwd)

    def test_the_launch_hook_lets_a_resume_through_when_the_run_did_not_stop_on_verification(self):
        self.start_phase_one()

        self.assert_launch_hook_passes("code", "resume")

        self.set_state(stage="stopped", stopReason="coder-cap")

        self.assert_launch_hook_passes("code", "resume")

    def test_resume_from_a_new_session_at_a_closing_phase_invokes_its_skill_again(self):
        self.on_feature_branch()
        self.finish_phase_one()
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)
        self.assertEqual("skill", self.state()["stage"])
        before = self.state_bytes()
        self.env["CLAUDE_CODE_SESSION_ID"] = self.NEW_SESSION

        out = self.step("resume")

        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("`/refactor +deep`", out)
        self.assertIn("The phase's own plan section follows", out)
        self.assertIn("Sweep.", out)
        self.assertIn("skill-done pass`", out)
        self.assertIn("`skill-done fail --finding", out)
        self.assertEqual(before, self.state_bytes())

    def test_resume_at_a_closing_phase_keeps_the_run_notes_it_started_with(self):
        self.on_feature_branch()
        self.finish_phase_one()
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan, "--phase", "4", "build", "with", "two", "jobs")
        self.env["CLAUDE_CODE_SESSION_ID"] = self.NEW_SESSION

        out = self.step("resume")

        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("Run notes from the user. They bind this run; the plan stays the spec:\nbuild with two jobs", out)

    PLANLESS_RESTART = 'ask the user for the task text, then run `start --restart --task "<the task text>"`'

    def start_a_run_with_no_plan(self):
        self.step("start", "--task", "fix the typo")
        self.assertIsNone(self.state()["plan"])

    def test_each_ask_for_a_run_with_no_plan_names_a_restart_with_the_task_text(self):
        def stop_the_coder_on_its_report():
            self.hook("coder", "BEHAVIOR: none\nblocked on two steps")
            self.step("resume")
            self.assertEqual("stopped", self.state()["stage"])

        asks = [
            ("fallback", lambda: self.set_state(dispatchAt=None)),
            ("coder cap", lambda: self.set_state(stage="stopped", stopReason="coder-cap", dispatchAt=None)),
            ("stopped coder", stop_the_coder_on_its_report),
        ]
        for label, reach_the_ask in asks:
            with self.subTest(label):
                self.setUp()
                self.start_a_run_with_no_plan()
                reach_the_ask()

                self.step("resume")

                self.assertIn(self.PLANLESS_RESTART, self.said())

    def test_the_coder_cap_stop_of_a_run_with_no_plan_names_a_restart_with_the_task_text(self):
        self.start_a_run_with_no_plan()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        restart_words = self.own_command("start --restart")
        self.assertIn(f'ask the user for the task text, then run `{restart_words} --task "<the task text>"`', out)

    def test_resume_after_a_coder_stopped_on_its_report_asks_for_the_users_answer(self):
        self.stop_the_coder_on_a_blocked_report()
        before = self.state_bytes()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("a1", self.said())
        self.assertIn("SendMessage", self.said())
        self.assertIn("tick 1", self.said())
        self.assertIn("start --restart", self.said())
        self.assertEqual(before, self.state_bytes())

    def end_the_main_sessions_turn(self):
        # The main session's Stop event runs the say-hook while the /code fork still works.
        stop_event = json.dumps({"cwd": str(self.repo), "hook_event_name": "Stop"})
        base.run(self.repo, self.env, "say-hook", stdin=stop_event)

    def question_file_named_in(self, out):
        ask_line = next(line for line in out.splitlines() if line.startswith("The question for the user is in "))
        question_path = ask_line.removeprefix("The question for the user is in ").removesuffix(". Hand back.")
        return pathlib.Path(question_path)

    def test_the_question_for_a_stopped_coder_outlives_the_main_sessions_stop_hook(self):
        self.stop_the_coder_on_a_blocked_report()

        out = self.step("resume")
        self.end_the_main_sessions_turn()

        question_text = self.question_file_named_in(out).read_text()
        self.assertIn("## Question for the user", question_text)
        self.assertIn("agent a1 with SendMessage", question_text)

    def test_resume_with_the_users_answer_from_a_stopped_coder_carries_the_answer_to_the_question(self):
        self.stop_the_coder_on_a_blocked_report()
        self.end_the_main_sessions_turn()
        before = self.state_bytes()

        out = self.step("resume", "use the v2 endpoint")
        self.end_the_main_sessions_turn()

        self.assertIn("ACTION: ask-user", out)
        question_text = self.question_file_named_in(out).read_text()
        answer_step = "The user answered: use the v2 endpoint. Send that answer to agent a1 with SendMessage"
        self.assertIn(answer_step, question_text)
        self.assertEqual(before, self.state_bytes())

    def test_the_next_verb_clears_the_answered_question(self):
        self.stop_the_coder_on_a_blocked_report()
        out = self.step("resume")
        question_file = self.question_file_named_in(out)

        self.step("status")
        self.assertIn("## Question for the user", question_file.read_text())
        self.step("resume")
        self.step("tick", "1")

        self.assertNotIn("## Question for the user", question_file.read_text())

    # ---------- the wait caps ----------

    def test_resume_after_the_review_cap_with_no_message_sent_asks_and_changes_nothing(self):
        self.stop_the_review_at_the_wait_cap()
        before = self.state_bytes()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("SendMessage", self.said())
        self.assertIn("review-again", self.said())
        self.assertEqual(before, self.state_bytes())

    def test_the_coder_cap_with_a_launch_id_is_resumed_by_that_agents_hand_back(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="c1")
        self.assertEqual("c1", self.state()["stop"]["agentId"])
        self.send_message("c1")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT, agent_id="c1")

        out = self.step("resume")

        self.assertIn("AGENT: review-loop", out)

    def test_a_restart_over_the_coder_cap_refuses_until_that_coder_is_stopped(self):
        cap_stop = self.stop_the_coder_at_the_wait_cap(launched_as="c1")
        self.assertIn("stop coder c1 with TaskStop", cap_stop)
        before = self.state_bytes()

        refused = self.step("start", "--restart")

        self.assertTrue(refused.startswith("Refused: coder c1 of the stopped run has not handed back"), refused)
        self.assertIn(f"COMMAND: {self.own_command('start --coder-stopped --restart')}", refused)
        self.assertEqual(before, self.state_bytes())

        restarted = self.step("start", "--coder-stopped", "--restart")

        self.assertIn("AGENT: coder", restarted)

    def test_a_restart_over_the_coder_cap_goes_on_once_that_coder_handed_back(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="c1")
        self.hook("coder", self.CODER_REPORT, agent_id="c1")

        out = self.step("start", "--restart")

        self.assertIn("AGENT: coder", out)

    def test_the_coder_cap_with_no_launch_record_asks_for_a_restart(self):
        self.stop_the_coder_at_the_wait_cap()
        self.assertEqual("coder-cap", self.state()["stop"]["kind"])

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("start --restart", self.said())

    def test_a_resumed_coder_that_reaches_the_cap_again_keeps_the_resume_text_and_has_no_stop_reason(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="c1")
        self.send_message("c1")
        self.set_state(resumableCoderAt=time.time() - 100, resumeWaitAt=time.time() - 100)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn("coder c1 with SendMessage", out)
        self.assertIn("start --restart", out)
        self.assertEqual("c1", self.state()["stop"]["agentId"])
        self.assertEqual("coder-resumable", self.state()["stop"]["kind"])

    def test_the_plan_coder_at_the_cap_says_only_the_phase_coder_resumes_and_start_restart_dispatches_it(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        self.assertEqual("plan-coder", self.state()["stage"])
        # The coder's own report sits just before this dispatch, so the dispatch time stays and the waits run to the
        # cap.
        self.wait_env(0.5, "0.1")

        out = self.step("resume")
        while "ACTION: wait" in out:
            out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn("plan-edit coder cannot be resumed", out)
        self.assertIn("start --restart", out)
        self.assertIn("To dispatch the phase coder again", out)
        self.assertEqual(("stopped", "coder-cap"), (self.state()["stage"], self.state()["stop"]["kind"]))

    def test_the_plan_coder_cap_stop_of_a_single_phase_deep_run_restarts_with_the_phase_and_the_modifier(self):
        self.start_phase_one("--phase", "1", "+deep")
        self.set_state(stage="plan-coder", dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertIn("plan-edit coder cannot be resumed", out)
        self.assertIn(f"run `{self.own_command('start --restart')} --phase 1 +deep`", out)

    def test_the_restart_ask_for_a_deep_run_with_no_plan_puts_the_modifier_before_the_task_flag(self):
        self.step("start", "+deep", "--task", "fix the typo")
        self.set_state(stage="stopped")

        self.step("resume")

        self.assertIn('then run `start --restart +deep --task "<the task text>"`', self.said())

    # ---------- a review-loop hand-back counts only from the agent the review was launched as ----------

    def test_a_review_loop_hand_back_from_another_agent_is_saved_and_never_answers_the_pending_review(self):
        self.coder_round()
        self.launch_the_pending_review("a1")
        self.hook("review-loop", self.LOOP_OK, agent_id="other")
        self.wait_env(0)

        out = self.step("resume")

        self.assertIn("other", [event["agent_id"] for event in self.events_named("handback")])
        self.assertNotIn("Phase 1 marked done", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertIsNone(self.gate_mark())
        self.assertEqual("review", self.state()["stage"])
        self.hook("review-loop", self.LOOP_OK, agent_id="a1")
        self.assertIn("Phase 1 marked done", self.step("resume"))

    def test_with_no_launch_record_no_review_loop_hand_back_matches(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK, agent_id="a1", launched=False)
        self.wait_env(0)

        out = self.step("resume")

        self.assertNotIn("Phase 1 marked done", out)
        self.assertIn("ACTION: stop", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertIsNone(self.gate_mark())

    def test_a_review_loop_resumed_with_send_message_keeps_its_launch_id_and_another_id_is_ignored(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.hook("review-loop", self.ASK, agent_id="other")
        self.hook("review-loop", self.LOOP_OK, agent_id="r1")

        out = self.step("resume")

        self.assertIn("Phase 1 marked done", out)
        self.assertNotIn("keep?", out + self.said())

    def test_the_hand_back_of_a_coder_that_was_never_launched_does_not_count(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT, agent_id="a1", launched=False)

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn("No coder report was saved", out)
        self.assertNotIn("AGENT: review-loop", out)

    # ---------- a report whose launch row never reached the log ----------

    def test_a_resume_takes_the_finished_report_of_a_coder_whose_launch_was_never_logged(self):
        self.begin_coder()
        self.age_dispatches(120)
        self.set_state(dispatchAt=time.time() - 120)
        self.hook("coder", self.CODER_REPORT, agent_id="a1", launched=False)
        self.wait_env(5, "0.2")

        out = self.step("resume")

        self.assertNotIn("no Agent call for it was launched", out)
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual(2, len(self.events_named("dispatch")))

    def test_a_resume_still_prints_the_dispatch_again_when_only_another_agents_report_is_logged(self):
        self.begin_coder()
        self.age_dispatches(120)
        self.set_state(dispatchAt=time.time() - 120)
        self.hook("review-loop", self.LOOP_OK, agent_id="a1", launched=False)
        self.wait_env(5, "0.2")

        out = self.step("resume")

        self.assertIn("no Agent call for it was launched", out)

    def test_a_resume_ignores_the_report_of_an_earlier_coder_round_when_the_new_dispatch_has_no_launch(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT, agent_id="a1", launched=False)
        self.age_dispatches(240)
        self.set_state(dispatchAt=time.time() - 120)
        self.wait_env(5, "0.2")

        out = self.step("resume")

        self.assertIn("no Agent call for it was launched", out)
        self.assertNotIn("AGENT: review-loop", out)

    def test_a_resume_inside_the_launch_grace_does_not_take_an_unlaunched_report(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT, agent_id="a1", launched=False)
        self.wait_env(1, "0.2")

        out = self.step("resume")

        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual(1, len(self.events_named("dispatch")))
        self.assertIn("ACTION: wait", out)

    # ---------- --help and refused answers ----------

    def test_help_after_a_verb_prints_its_usage_and_changes_nothing(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="a1")
        before = self.state_bytes()
        question_before = (self.repo / ".git/code-step/question.md").read_bytes()

        verbs = ("resume", "decide", "abort", "status", "review-again", "verify", "tick", "asks-done", "skill-done",
                 "hook", "stop-hook")
        for verb in verbs:
            for flag in ("--help", "-h"):
                finished = base.run(self.repo, self.env, verb, flag)
                self.assertEqual(0, finished.returncode, (verb, flag))
                self.assertIn(f"usage: code_step.py {verb}", finished.stdout)
                self.assertNotIn("ACTION:", finished.stdout)
                self.assertNotIn("The user answered", finished.stdout)
                self.assertEqual(before, self.state_bytes(), (verb, flag))
        self.assertEqual(question_before, (self.repo / ".git/code-step/question.md").read_bytes())

    def test_a_former_resume_alias_is_refused_as_an_unknown_verb_and_changes_nothing(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="a1")
        before = self.state_bytes()

        for alias in ("after-coder", "after-review", "after-plan-edit"):
            with self.subTest(alias):
                refused = base.run(self.repo, self.env, alias)

                self.assertNotEqual(0, refused.returncode)
                self.assertIn("usage: code_step.py start|resume|decide", refused.stderr)
                self.assertEqual("", refused.stdout)
                self.assertEqual(before, self.state_bytes())

    def test_a_resume_answer_with_a_dashed_later_word_is_accepted_and_a_dashed_first_word_is_refused(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="a1")
        self.set_state(stage="stopped", resumableCoderId="a1", resumableCoderAt=time.time())
        before = self.state_bytes()

        for dashed_answer in ("-v", "--hepl"):
            with self.subTest(dashed_answer):
                refused = base.run(self.repo, self.env, "resume", dashed_answer)

                self.assertEqual(2, refused.returncode)
                self.assertIn("an answer must not start with '-'", refused.stderr)
                self.assertEqual("", refused.stdout)
                self.assertEqual(before, self.state_bytes())

        accepted = base.run(self.repo, self.env, "resume", "use", "the", "-v", "flag")

        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertIn("The user answered: use the -v flag.", self.said())

    def test_a_state_file_in_the_old_stop_format_resumes_the_coder_as_before(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="a1")
        self.set_state(stop=None, stage="stopped", stopReason="coder-cap", resumableCoderId="a1",
                       resumableCoderAt=time.time() - 100, resumeWaitAt=time.time() - 100)

        coder_out = base.run(self.repo, self.env, "resume", "use", "the", "flag")

        self.assertEqual(0, coder_out.returncode, coder_out.stderr)
        self.assertIn("The user answered: use the flag.", self.said())
        self.assertEqual(("coder-resumable", "a1"), (self.state()["stop"]["kind"], self.state()["stop"]["agentId"]))
        for old_key in ("stopReason", "resumableCoderId", "resumableCoderAt", "resumeWaitAt"):
            self.assertNotIn(old_key, self.state())

    def test_a_state_file_with_the_old_resumable_review_key_resumes_the_review_as_before(self):
        self.begin_coder()
        self.set_state(stage="stopped", resumableReview=time.time(), reviewScriptPid=os.getpid())
        review_out = base.run(self.repo, self.env, "resume")

        self.assertEqual(0, review_out.returncode, review_out.stderr)
        self.assertIn("The resumed review-loop has not handed back yet", review_out.stdout)
        self.assertEqual("review-resumable", self.state()["stop"]["kind"])
        for old_key in ("stopReason", "resumableReview"):
            self.assertNotIn(old_key, self.state())

    # ---------- a stale phase ----------

    def renumber_phase_one(self):
        renumbered = self.plan_text().replace("## Phase 1: Walking skeleton", "## Phase 9: Other")
        (self.repo / self.plan).write_text(renumbered)

    def plan_with_phase_one_test_file_changed(self):
        changed = self.plan_text().replace("**File**: `backend/src/orders.test.ts`",
                                           "**File**: `backend/src/other.test.ts`")
        self.assertNotEqual(changed, self.plan_text())
        return changed

    def test_a_resume_of_a_run_whose_phase_text_changed_offers_to_drop_it_and_start_the_next_open_phase(self):
        self.begin_coder()
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        question_text = (self.repo / ".git/code-step/question.md").read_text()
        self.assertIn("text of Phase 1", question_text)
        self.assertIn("changed since the run started", question_text)
        self.assertIn(self.own_command(f"start --restart {self.plan}"), question_text)
        self.assertEqual("coder", self.state()["stage"])

    def test_a_stale_resume_offers_the_restart_with_the_modifier(self):
        self.begin_coder(start_options=("+deep",))
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        self.step("resume")

        question_text = (self.repo / ".git/code-step/question.md").read_text()
        self.assertIn(self.own_command(f"start --restart {self.plan} +deep"), question_text)

    def test_after_coder_over_a_changed_phase_goes_on_to_the_review_without_a_stale_question(self):
        self.begin_coder()
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())
        self.hook("coder", self.CODER_REPORT)

        out = self.step("resume")

        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn("stale", out)

    def test_a_resume_during_the_plan_coder_does_not_call_an_edited_phase_stale(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        self.assertEqual("plan-coder", self.state()["stage"])
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        out = self.step("resume")

        self.assertNotIn("ACTION: ask-user", out)
        self.assertNotIn("stale", out)
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])

    def test_a_resume_during_the_impact_coder_does_not_call_an_edited_phase_stale(self):
        self.coder_round(self.IMPACT_REPORT)
        self.assertEqual("impact-coder", self.state()["stage"])
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        out = self.step("resume")

        self.assertNotIn("stale", out)
        self.assertNotIn("stale", self.said())
        question_path = self.repo / ".git/code-step/question.md"
        self.assertTrue(not question_path.exists() or "stale" not in question_path.read_text())
        self.assertEqual("impact-coder", self.state()["stage"])

    def test_a_resume_at_a_plan_format_stop_does_not_call_an_edited_phase_stale(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.break_manual_section()
        self.step("resume")
        self.assertEqual("plan-format", self.state()["stop"]["kind"])
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        self.step("resume")

        self.assertIn("verify", self.said())
        self.assertNotIn("stale", self.said())

    def test_a_resume_answer_over_a_stale_phase_says_the_phase_is_stale_not_that_no_coder_waits(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="a1")
        self.set_state(stage="stopped", resumableCoderId="a1", resumableCoderAt=time.time())
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        out = self.step("resume", "use the -v flag")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("stale", (self.repo / ".git/code-step/question.md").read_text())
        self.assertNotIn("no stopped coder waits", out)

    def test_a_resume_while_the_review_script_runs_does_not_call_the_phase_stale(self):
        self.begin_coder()
        self.set_state(stage="review", reviewScriptPid=os.getpid())
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        finished = base.run(self.repo, self.env, "resume")

        self.assertEqual(0, finished.returncode)
        self.assertIn("no hand-back can be matched", finished.stdout)
        self.assertNotIn("stale", finished.stdout)
        self.assertNotIn("stale", self.said())
        self.assertEqual(os.getpid(), self.state()["reviewScriptPid"])

    def test_a_resume_at_the_review_cap_while_the_review_script_runs_does_not_call_the_phase_stale(self):
        self.begin_coder()
        self.set_state(stage="stopped", resumableReview=time.time(), reviewScriptPid=os.getpid())
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        finished = base.run(self.repo, self.env, "resume")

        self.assertEqual(0, finished.returncode)
        self.assertIn("The resumed review-loop has not handed back yet", finished.stdout)
        self.assertNotIn("stale", finished.stdout)
        self.assertNotIn("ACTION: ask-user", finished.stdout)
        self.assertEqual(os.getpid(), self.state()["reviewScriptPid"])

    def test_a_resume_of_a_review_with_no_live_script_asks_about_the_changed_phase(self):
        reaped_child = subprocess.Popen([sys.executable, "--version"], stdout=subprocess.DEVNULL)
        reaped_child.wait()
        for label, script_pid in (("script died", reaped_child.pid), ("no script pid", None)):
            with self.subTest(label):
                self.setUp()
                self.begin_coder()
                self.set_state(stage="review", reviewScriptPid=script_pid)
                (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

                out = self.step("resume")

                self.assertIn("ACTION: ask-user", out)
                self.assertIn("changed since the run started",
                              (self.repo / ".git/code-step/question.md").read_text())

    def test_a_stale_question_names_the_phase_lines_that_changed(self):
        self.begin_coder()
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        self.step("resume")

        question_text = (self.repo / ".git/code-step/question.md").read_text()
        self.assertRegex(question_text, r"was: [^;]*backend/src/orders\.test\.ts")
        self.assertRegex(question_text, r"now: [^;]*backend/src/other\.test\.ts")

    def test_a_stale_question_for_a_blank_line_only_edit_has_no_empty_parentheses(self):
        self.begin_coder()
        reordered = self.plan_text().replace("**File**: `backend/src/orders.test.ts`\n",
                                             "\n**File**: `backend/src/orders.test.ts`\n", 1)
        self.assertNotEqual(reordered, self.plan_text())
        (self.repo / self.plan).write_text(reordered)

        self.step("resume")

        question_path = self.repo / ".git/code-step/question.md"
        self.assertTrue(question_path.exists())
        question_text = question_path.read_text()
        self.assertIn("changed since the run started", question_text)
        self.assertNotIn("()", question_text)

    def test_a_resume_at_a_plan_fix_stop_with_an_unreadable_plan_goes_on_to_the_stop(self):
        self.begin_coder()
        self.set_state(stage="stopped", stopReason="verification")
        (self.repo / self.plan).unlink()

        self.step("resume")

        self.assertIn("verify", self.said())
        self.assertNotIn("cannot be read", self.said())

    def test_a_resume_of_a_run_whose_plan_file_is_gone_asks_about_the_stale_phase(self):
        self.begin_coder()
        (self.repo / self.plan).unlink()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("cannot be read", (self.repo / ".git/code-step/question.md").read_text())

    def test_a_resume_of_a_run_whose_phase_left_the_plan_says_so(self):
        runs = [
            ("coder out", {}),
            ("verification stop", {"stage": "stopped", "stopReason": "verification"}),
            ("plan-format stop", {"stage": "stopped", "stopReason": "plan-format"}),
        ]
        for label, saved_state in runs:
            with self.subTest(label):
                self.setUp()
                self.begin_coder()
                self.set_state(**saved_state)
                plan_before = self.plan_text()
                self.renumber_phase_one()
                self.assertNotEqual(plan_before, self.plan_text())

                out = self.step("resume")

                self.assertIn("ACTION: ask-user", out)
                question_text = (self.repo / ".git/code-step/question.md").read_text()
                self.assertIn("Phase 1 is no longer in", question_text)

    def test_a_phase_ticked_by_the_runs_own_gates_is_not_stale(self):
        self.begin_coder()
        ticked = self.plan_text().replace(
            "- [ ] **Test-verified**: orders pass - `npx vitest run`",
            "- [x] **Test-verified**: orders pass - `npx vitest run`\n  - Done: ran it", 1)
        self.assertNotEqual(self.plan_text(), ticked)
        (self.repo / self.plan).write_text(ticked)
        self.hook("coder", self.CODER_REPORT)

        out = self.step("resume")

        self.assertNotIn("stale", out)
        self.assertIn("AGENT: review-loop", out)

    def test_a_resume_after_a_phase_was_inserted_above_the_runs_phase_while_the_coder_was_out_is_stale(self):
        self.begin_coder()
        inserted = self.plan_text().replace("## Phase 1: Walking skeleton",
                                            "## Phase 1: Inserted work\n\nOther work.\n\n## Phase 8: Walking skeleton")
        self.assertNotEqual(self.plan_text(), inserted)
        (self.repo / self.plan).write_text(inserted)
        self.hook("coder", self.CODER_REPORT)

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("changed since the run started", (self.repo / ".git/code-step/question.md").read_text())

    def test_a_resume_at_the_asks_after_the_review_loop_edited_the_phase_text_is_not_stale(self):
        self.coder_round()
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())
        self.hook("review-loop", self.ASK)
        self.step("resume")
        self.assertEqual("asks", self.state()["stage"])

        out = self.step("resume")

        self.assertNotIn("stale", self.said())
        self.assertEqual("asks", self.state()["stage"])
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("Proposed change: export o as a const", (self.repo / ".git/code-step/question.md").read_text())

    def test_a_plan_edit_after_the_review_loop_handed_back_is_still_stale(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("resume")
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("changed since the run started", (self.repo / ".git/code-step/question.md").read_text())

    def test_a_resume_after_an_adopted_plan_edit_and_a_review_loop_edit_is_not_stale(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        (self.repo / self.plan).write_text(self.plan_with_phase_one_test_file_changed())
        self.hook("coder", "Rewrote the step.")
        self.step("resume")
        self.assertEqual("review", self.state()["stage"])
        reworded = self.plan_text().replace("backend/src/other.test.ts", "backend/src/orders.spec.ts")
        (self.repo / self.plan).write_text(reworded)
        self.hook("review-loop", self.ASK)

        self.step("resume")

        self.assertNotIn("stale", self.said())
        self.assertEqual("asks", self.state()["stage"])

    def test_start_over_an_open_stale_run_names_the_stale_phase_in_the_refusal(self):
        self.begin_coder()
        self.renumber_phase_one()

        out = self.step("start")

        self.assertIn("The run is stale: Phase 1 is no longer in", out)

    # ---------- a stop with a way out ----------

    def test_start_restart_with_text_over_a_stopped_plan_run_dispatches_the_coder_with_the_text_as_notes(self):
        self.coder_round()
        self.hook("review-loop", BLOCKER_PACKET)
        self.step("resume")
        self.assertEqual("stopped", self.state()["stage"])

        out = self.step("start", "--restart", "the", "tool", "is", "installed", "now")

        self.assertNotIn("has open phases", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("the tool is installed now", out)
        self.assertEqual(self.plan, self.state()["plan"])

    def test_start_restart_with_text_and_no_saved_plan_stays_task_text(self):
        out = self.step("start", "--restart", "fix", "the", "typo")

        self.assertIn("AGENT: coder", out)
        self.assertIsNone(self.state().get("plan"))
        self.assertIn("fix the typo", out)
        self.assertNotIn("Run notes from the user", out)

    def test_review_again_is_accepted_after_each_review_stop_that_names_it(self):
        review_again = self.own_command("review-again")
        stops = [
            ("critical blocker", BLOCKER_PACKET, "critical-blocker",
             "the review found a critical blocker", review_again),
            ("setup fault", SETUP_FAULT_PACKET, "setup-fault",
             "the review's full check could not run here", review_again),
            ("check unverified", UNVERIFIED_PACKET, "check-unverified",
             "with stop reason check-unverified.", "When the cause is fixed, run `review-again`."),
        ]
        for label, packet, stop_reason, said_text, resumed_question in stops:
            with self.subTest(label):
                self.setUp()
                question_path = self.repo / ".git/code-step/question.md"
                self.coder_round()
                self.hook("review-loop", packet)
                stop = self.step("resume")
                self.assertEqual(stop_reason, self.state()["stop"]["kind"])
                self.assertIn(review_again, question_path.read_text())
                self.assertIn("ACTION: stop", stop)

                resumed = self.step("resume")
                self.assertIn("ACTION: ask-user", resumed)
                self.assertIn("## Question for the user", question_path.read_text())
                self.assertIn(resumed_question, question_path.read_text())
                self.assertIn(said_text, self.said())

                again = self.step("review-again")

                self.assertIn("AGENT: review-loop", again)
                self.assertEqual("review", self.state()["stage"])

    # ---------- a review that handed back clean over an unreviewed change ----------

    def forget_the_hand_back_store(self):
        # With the stored hand-backs gone, a clean review packet matches no recorded review of the change.
        shutil.rmtree(self.tmp / "handback-store")

    def test_a_resume_after_a_false_clean_stop_dispatches_the_review_again(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.forget_the_hand_back_store()
        self.step("resume")
        self.assertEqual("false-clean", self.state()["stop"]["kind"])

        out = self.step("resume")

        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])
        self.assertNotIn("stop", self.state())

    # ---------- a restart that keeps the phase ----------

    def test_a_resume_at_a_verification_stop_does_not_call_a_changed_verification_command_stale(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.step("resume")
        self.assertEqual("verification", self.state()["stop"]["kind"])
        (self.repo / self.plan).write_text(self.plan_text().replace("`npx vitest run`", "`npx vitest run --silent`"))

        self.step("resume")

        self.assertIn("verify", self.said())
        self.assertNotIn("stale", self.said())

    def test_verify_takes_the_users_fixed_verification_lines_as_the_phase_text(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.step("resume")
        self.assertEqual("verification", self.state()["stop"]["kind"])
        (self.repo / self.plan).write_text(self.plan_text().replace("`npx vitest run`", "`npx vitest run --silent`"))

        self.step("verify")

        self.assertIn("`npx vitest run --silent`", self.state()["phaseText"])

    def test_start_restart_with_text_over_a_stopped_single_phase_run_restarts_that_phase(self):
        self.step("start", self.plan, "--phase", "2")
        self.pass_coder_gate()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals exist\nREVIEW: recommended")
        self.step("resume")
        self.hook("review-loop", BLOCKER_PACKET)
        self.step("resume")
        self.assertEqual("stopped", self.state()["stage"])
        self.assertEqual("2", self.state()["onlyPhase"])

        out = self.step("start", "--restart", "the", "tool", "is", "installed", "now")

        self.assertIn("AGENT: coder", out)
        self.assertIn("Phase 2", out)
        self.assertEqual("2", self.state()["phase"])
        self.assertEqual("2", self.state()["onlyPhase"])


# The tests inherited from the fixture class run in test_code_step.py: leave them out here.
for inherited_test in [name for name in dir(base.CodeStepTest) if name.startswith("test_")]:
    if inherited_test not in vars(ResumeTest):
        setattr(ResumeTest, inherited_test, None)


if __name__ == "__main__":
    base.unittest.main()
