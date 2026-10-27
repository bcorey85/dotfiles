"""The `resume` verb of code_step.py, the refusals of `start` and of the guarded verbs, and the match of a
review-loop hand-back to the review it was launched for.

Each test gives a saved state, runs one verb and checks what the main session is told and what the saved state
became. The fixtures are those of test_code_step.py; its own tests run there, not here.

run: python3 -m unittest test_code_step_resume
"""
import json
import pathlib
import shutil
import time

import test_code_step as base

BLOCKER_PACKET = "status: critical-blocker\niter: 1\nblockers:\n  - finding: b\n    file_line: backend/src/orders.ts:1"


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

        out = self.step("start", "after-review")

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

    def test_start_with_a_plan_then_phase_and_its_id_starts_that_phase(self):
        self.finish_phase_one()

        out = self.step("start", self.plan, "Phase", "2")

        self.assertIn("ACTION: dispatch", out)
        self.assertEqual("2", self.state()["phase"])

    def test_start_with_a_plan_then_a_bare_phase_id_in_one_quoted_argument_starts_that_phase(self):
        self.finish_phase_one()

        out = self.step("start", f"{self.plan} 2")

        self.assertIn("ACTION: dispatch", out)
        self.assertEqual("2", self.state()["phase"])

    def test_start_with_a_phase_and_no_plan_before_task_text_is_refused_with_the_start_and_the_task_commands(self):
        self.finish_phase_one()
        before = self.state_bytes()

        out = self.step("start", "--phase", "2", "—", "brief")

        self.assert_refused_with_choices(out, "start --phase 2", "start --task '— brief'")
        self.assertIn("was not passed to the coder", out)
        self.assertEqual(before, self.state_bytes())

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

    def test_the_restart_text_of_a_deep_run_names_the_modifier(self):
        said = self.restart_text_after_a_stop("+deep")

        self.assertIn("run `start --restart +deep`", said)
        self.assertNotIn("--phase", said)

    def test_the_restart_text_of_a_single_phase_run_names_the_phase(self):
        said = self.restart_text_after_a_stop("--phase", "1")

        self.assertIn("run `start --restart --phase 1`", said)

    def test_the_restart_text_of_a_single_phase_fast_run_names_the_phase_and_the_modifier(self):
        said = self.restart_text_after_a_stop("--phase", "1", "+fast")

        self.assertIn("run `start --restart --phase 1 +fast`", said)

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

    # ---------- resume by saved state ----------

    def test_resume_with_no_saved_run_does_what_a_bare_start_does(self):
        other_repo = self.tmp / "other"
        shutil.copytree(self.repo, other_repo, symlinks=True)

        resumed = self.step("resume")
        started = base.run(other_repo, self.env, "start").stdout

        self.assertEqual(started.replace(str(other_repo), str(self.repo)), resumed)

    def test_resume_with_no_dispatch_time_asks_for_the_saved_state_and_keeps_the_baseline(self):
        self.begin_coder()
        self.set_state(dispatchAt=None)
        before = self.state_bytes()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("The run is at stage coder.", self.said())
        self.assertEqual(before, self.state_bytes())

    def test_the_old_name_of_the_review_step_is_an_alias_of_resume(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-coder")

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
        self.assertEqual("stopped", self.state()["stage"])
        before = self.state_bytes()

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"`{self.own_command('status')}`", self.said())
        self.assertIn("start --restart", self.said())
        self.assertEqual(before, self.state_bytes())

    def test_resume_at_a_stop_for_a_guarded_verb_prints_the_state_and_names_that_verb(self):
        self.leave_unreadable_packet()
        self.step("resume")
        self.assertEqual("invalid-packet", self.state()["stopReason"])

        self.step("resume")

        self.assertIn("stage stopped with stop reason invalid-packet", self.said())
        self.assertIn("`review-again`", self.said())
        self.assertNotIn("start --restart", self.said())

    def test_resume_at_a_failed_verification_stop_names_verify(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("resume"))
        self.assertEqual("verification", self.state()["stopReason"])

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn("stage stopped with stop reason verification", self.said())
        self.assertIn("`verify`", self.said())

    def test_resume_from_a_new_session_at_a_closing_phase_invokes_its_skill_again(self):
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
        self.assertIn("`skill-done fail`", out)
        self.assertEqual(before, self.state_bytes())

    PLANLESS_RESTART = 'ask the user for the task text, then run `start --restart --task "<the task text>"`'

    def start_a_run_with_no_plan(self):
        self.step("start", "--task", "fix the typo")
        self.assertIsNone(self.state()["plan"])

    def test_the_fallback_ask_for_a_run_with_no_plan_names_a_restart_with_the_task_text(self):
        self.start_a_run_with_no_plan()
        self.set_state(dispatchAt=None)

        self.step("resume")

        self.assertIn(self.PLANLESS_RESTART, self.said())

    def test_the_coder_cap_ask_for_a_run_with_no_plan_names_a_restart_with_the_task_text(self):
        self.start_a_run_with_no_plan()
        self.set_state(stage="stopped", stopReason="coder-cap", dispatchAt=None)

        self.step("resume")

        self.assertIn(self.PLANLESS_RESTART, self.said())

    def test_the_ask_for_a_stopped_coder_of_a_run_with_no_plan_names_a_restart_with_the_task_text(self):
        self.start_a_run_with_no_plan()
        self.hook("coder", "BEHAVIOR: none\nblocked on two steps")
        self.step("resume")
        self.assertEqual("stopped", self.state()["stage"])

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

    def test_review_again_after_the_review_cap_dispatches_a_new_review_loop(self):
        self.stop_the_review_at_the_wait_cap()
        stopped_at = self.state()["resumableReview"]

        out = self.step("review-again")

        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn("resumableReview", self.state())
        self.assertGreater(self.state()["dispatchAt"], stopped_at)

    def test_the_coder_cap_with_a_launch_id_is_resumed_by_that_agents_hand_back(self):
        self.stop_the_coder_at_the_wait_cap(launched_as="c1")
        self.assertEqual("c1", self.state()["resumableCoderId"])
        self.send_message("c1")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT, agent_id="c1")

        out = self.step("resume")

        self.assertIn("AGENT: review-loop", out)

    def test_the_coder_cap_with_no_launch_record_asks_for_a_restart(self):
        self.stop_the_coder_at_the_wait_cap()
        self.assertEqual("coder-cap", self.state()["stopReason"])

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
        self.assertEqual("c1", self.state()["resumableCoderId"])
        self.assertNotIn("stopReason", self.state())

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
        self.assertEqual(("stopped", "coder-cap"), (self.state()["stage"], self.state()["stopReason"]))

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

# The tests inherited from the fixture class run in test_code_step.py: leave them out here.
for inherited_test in [name for name in dir(base.CodeStepTest) if name.startswith("test_")]:
    if inherited_test not in vars(ResumeTest):
        setattr(ResumeTest, inherited_test, None)


if __name__ == "__main__":
    base.unittest.main()
