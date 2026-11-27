"""Checks for the announced-step reason of staged_claim_gate.py: a main-session turn that ends saying it will do, or is
doing, a step it has not started is sent back once."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = toolkit_paths.GATES_DIR / "staged_claim_gate.py"
REASON_START = "Your message says you will do, or are doing, a step"


class AnnouncedStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write_turn(self, *, launches=True, later_turn=False, plain_agent_only=False):
        """A transcript: a turn start, then a background Bash and Agent launch, optionally a later turn start."""
        def record(content):
            return {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": content[0], "input": content[1]}]}}

        records = [{"type": "user", "message": {"role": "user", "content": "<bash-input>ls</bash-input>"}}]
        if plain_agent_only:
            records.append(record(("Agent", {"prompt": "label"})))
        elif launches:
            records.append(record(("Bash", {"command": "make test", "run_in_background": True})))
            records.append(record(("Agent", {"prompt": "label", "run_in_background": "true"})))
        if later_turn:
            records.append({"type": "user", "message": {"role": "user", "content": "<bash-input>pwd</bash-input>"}})
        transcript = self.tmp / "turn.jsonl"
        transcript.write_text("".join(json.dumps(entry) + "\n" for entry in records))
        return transcript

    def run_gate(self, message, event="Stop", stop_hook_active=False, transcript_path=""):
        payload = {"hook_event_name": event, "cwd": str(self.tmp), "last_assistant_message": message,
                   "stop_hook_active": stop_hook_active, "transcript_path": str(transcript_path)}
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, cwd=str(self.tmp), env=environment)
        self.assertEqual((finished.returncode, finished.stderr), (0, ""))
        return finished.stdout

    def assert_blocks(self, message, **options):
        output = self.run_gate(message, **options)
        self.assertTrue(output, f"expected a block for: {message}")
        decision = json.loads(output)
        self.assertEqual(decision["decision"], "block")
        self.assertIn(REASON_START, decision["reason"])

    def assert_passes(self, message, **options):
        self.assertEqual(self.run_gate(message, **options), "", f"expected a pass for: {message}")

    def test_future_step_with_nothing_started_blocks(self):
        self.assert_blocks("The scout scores 9/10. Next I'll look at the reviewer nits.")

    def test_present_claim_of_work_in_progress_blocks(self):
        self.assert_blocks("Next: I claimed the CLAUDE.md shrink item and I'm starting it now.")

    def test_starting_it_now_without_a_subject_blocks(self):
        self.assert_blocks("The queue item is claimed. Starting it now.")

    def test_step_that_waits_on_the_user_passes(self):
        self.assert_passes("Turn the gate off and I'll write the check and its test.")

    def test_conditional_step_passes(self):
        self.assert_passes("Once the pull is clean, I'll push the three commits.")

    def test_step_that_names_running_work_passes(self):
        self.assert_passes("The labeling agent is running in the background; I'll read its report when it lands.")

    def test_question_passes(self):
        self.assert_passes("I'll rename the module to scout_feeds?")

    def test_past_tense_report_passes(self):
        self.assert_passes("I moved three sections out of CLAUDE.md and committed them as 8b97cc31.")

    def test_quoted_announcement_passes(self):
        self.assert_passes('The session ended on "Next I\'ll look at the reviewer nits." with nothing running.')

    def test_second_stop_in_a_row_passes(self):
        self.assert_passes("Next I'll look at the reviewer nits.", stop_hook_active=True)

    def test_incident_progress_line_after_a_background_launch_passes(self):
        self.assert_passes("Next queue item: a new agent is working on it.", transcript_path=self.write_turn())

    def test_on_it_now_after_a_background_launch_passes(self):
        self.assert_passes("On it now.", transcript_path=self.write_turn())

    def test_progress_line_after_an_agent_call_with_no_background_key_passes(self):
        transcript = self.write_turn(plain_agent_only=True)
        self.assert_passes("Next queue item: a new agent is working on it.", transcript_path=transcript)

    def test_on_it_now_in_a_turn_with_no_launch_blocks(self):
        self.assert_blocks("On it now.", transcript_path=self.write_turn(launches=False))

    def test_progress_line_with_the_launch_in_an_earlier_turn_blocks(self):
        transcript = self.write_turn(later_turn=True)
        self.assert_blocks("Next queue item: a new agent is working on it.", transcript_path=transcript)

    def test_progress_line_in_a_turn_with_no_launch_blocks(self):
        self.assert_blocks("Starting it now.", transcript_path=self.write_turn(launches=False))

    def test_first_person_step_after_a_background_launch_still_blocks(self):
        transcript = self.write_turn()
        messages = ("I'll push them with the four closures at the end.", "I'm on it now.", "I'm working on it.",
                    "I am on it now.", "I am writing the check.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_blocks(message, transcript_path=transcript)

    def test_report_step_on_background_work_passes_after_a_launch_and_blocks_without_one(self):
        messages = ("I'll bring back the ranked list from the three scouts.",
                    "I will summarize the findings of the agents.",
                    "I'll collect and compile the results.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_passes(message, transcript_path=self.write_turn())
                self.assert_blocks(message, transcript_path=self.write_turn(launches=False))

    def test_report_step_with_the_launch_in_an_earlier_turn_blocks(self):
        transcript = self.write_turn(later_turn=True)
        self.assert_blocks("I'll bring back the ranked list from the three scouts.", transcript_path=transcript)

    def test_draft_blocks_with_first_person_promises_pass(self):
        messages = ("Here is the reply to send:\n```\nI am fixing the parser.\n```\nSend it as is.",
                    "Here is the reply to send:\n~~~text\nI'll fix the parser.\n~~~\nSend it as is.",
                    "Here is the reply to send:\n> I am fixing the parser.\n> I'll look at it today.\nSend it as is.",
                    "Draft:\n````\nI am fixing the parser.\n```\nstill inside\n````\nDone.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_stray_opening_fence_does_not_hide_a_later_announcement(self):
        self.assert_blocks("Draft:\n```\nI am fixing the parser.\nThe fence never closes.")

    def test_a_report_word_that_is_not_the_announced_action_still_blocks_after_a_launch(self):
        transcript = self.write_turn()
        for message in ("I'll push them and report back.", "I'm going to fix the report parser."):
            with self.subTest(message=message):
                self.assert_blocks(message, transcript_path=transcript)

    def test_a_report_action_joined_to_a_second_verb_blocks_after_a_launch(self):
        self.assert_blocks("I'll report the results and push them.", transcript_path=self.write_turn())

    def test_fence_line_with_an_info_string_does_not_close_a_draft_block(self):
        self.assert_passes("Draft:\n```\nI'll x\n```python\nI am fixing the parser.\n```\nDone.")

    def test_report_word_deep_in_a_first_person_sentence_blocks_after_a_launch(self):
        self.assert_blocks("I'll fix the bug report.", transcript_path=self.write_turn())
        self.assert_blocks("I'll fix the bug report.", transcript_path=self.write_turn(launches=False))

    def test_promise_outside_a_draft_block_still_blocks(self):
        self.assert_blocks("Draft:\n```\nI am fixing the parser.\n```\nNext I'll look at the reviewer nits.")
        self.assert_blocks("Draft:\n> I am fixing the parser.\nNext I'll look at the reviewer nits.")

    def test_steps_gated_by_a_date_a_clock_later_events_or_another_partys_notice_pass(self):
        messages = ("I'll run the weekly scan on Nov 29.", "I'll recheck at :47.", "I'll run the scan on Monday.",
                    "I'll check it tomorrow.", "I'll send later merges to `weekend-toolkit-fixes-v2`.",
                    "I'll act on their completion notices.",
                    "Once agent-evals-74 confirms the merge, I'll repoint it. Then I'll push the branch.",
                    "I'll repoint it once agent-evals-74 confirms.", "I'll run it after Nov 29.",
                    "I'll merge when the lane reports.",
                    "The suite is running in the background. Next I'll read its log.",
                    "1. Once the lane merges, I will repoint it.\n2. Then I will push the branch.",
                    "+ Once the lane merges, I will repoint it.\n+ Then I will push the branch.",
                    "1) Once the lane merges, I will repoint it.\n2) Then I will push the branch.",
                    "Once the lane merges, I'll repoint it. Then I'll push the branch. Next I'll tag it.",
                    "I'll push it at 4:30.", "I'll run it tonight.", "I'll fix it the next time it runs.",
                    "I'll merge it by Friday.", "I'll push it at 4:30pm.", "I'll push it at 4pm.",
                    "I'll run the scan on November 29th.", "I'll merge it by Dec 3.", "I'll act on the result.",
                    "I'll act on its review report.",
                    "- Once the lane merges, I will repoint it.\n- Then I will push the branch.",
                    "Once the lane merges, I'll repoint it. After that I'll push the branch.",
                    "Once the lane merges, I'll repoint it. Next step: I'll push the branch.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_ungated_and_own_step_ordering_promises_still_block(self):
        messages = ("I'll run the suite next.", "I'll work on it.", "I'll look at the diff.", "I'll fix that later.",
                    "I'll check who holds them before starting any of them.",
                    "- One merge line, which I'll write up at the end.",
                    "The tree is clean. Then I'll push the branch.", "The tree is clean. Next I'll push the branch.",
                    "I'll list the open items in my final report.", "I'll look at it later this week.",
                    "I'll do it later as tests.", "I'll fix that later perhaps.",
                    "If it fails we stop.\n\nNext steps: I'll run the suite.",
                    "Once the lane merges, I'll repoint it. The tree is clean. Then I'll push the branch.",
                    "I'll fix that later is fine.", "I'll redo it later its way.",
                    "I'll fix it later afterwards.", "I'll fix it later towards the end.",
                    "I'll fix it later yes.", "I'll fix it later thus.",
                    "I'll fix that later across the board.", "I'll fix that later plus the docs.",
                    "I'll fix that later access.", "I'll fix that later nonetheless.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_blocks(message)

    def test_each_excluded_word_after_later_still_blocks(self):
        words = ("this", "its", "is", "was", "as", "perhaps", "always", "anyways", "sometimes", "besides", "versus",
                 "afterwards", "towards", "yes", "thus", "plus", "does", "has", "us", "whereas", "his", "hers",
                 "ours", "theirs", "nowadays", "upstairs", "downstairs", "alas", "regardless", "less", "across")
        for word in words:
            with self.subTest(word=word):
                self.assert_blocks(f"I'll fix it later {word}.")

    def test_a_negated_announcement_passes(self):
        for message in ("I'm starting no lane for it.", "I'll start nothing for it.", "I will do none of them.",
                        "I'll not touch the branch.", "I'm going to do nothing.",
                        "I will not act on any timer prompt.", "I'll not start the lane.",
                        "I'll do nothing else today.", "I'll send nothing.", "I'll launch no lane.",
                        "I'll open none of them.", "I'll begin nothing.", "I'll run no lane.",
                        "I'll make no change.", "I'll not run it.", "I'll not begin it.", "I'll not launch it.",
                        "I'll not open it.", "I'll not send it.", "I'll not make it."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_an_announcement_beside_a_negated_one_still_blocks(self):
        for message in ("I'll start the lane.", "I'll remove no-op calls.", "I'll confirm nothing regressed.",
                        "I'll check no other caller reads it.", "I'll fix none other than the gate.",
                        "I'll not only fix the gate but also rerun the suite.", "I'll do nothing but rerun the suite.",
                        "I'll not forget to run the suite.", "I'll waste no time on the fix.",
                        "I'll no doubt rerun the suite.", "I'll not hesitate to rerun the suite.",
                        "I'll not neglect the tests.", "I'll no longer skip it.",
                        "I'll do nothing except rerun the suite.", "I'll do nothing besides rerun the suite.",
                        "I'll do nothing beyond a rerun of the suite.", "I'll touch nothing apart from the gate.",
                        "I'll not skip the suite this time.", "I'll not ignore the failing test.",
                        "I'll not omit the docs update.", "I'll not leave the suite red.",
                        "I'll not delay the rerun.", "I'll not wait to rerun the suite.",
                        "I'll not merely rerun the suite.", "I'll not simply rerun the suite.",
                        "I'll do no more than rerun the suite.", "I'll do nothing more than rerun the suite.",
                        "I'll do no less than rerun the suite.", "I'll do nothing less than rerun the suite.",
                        "I'll not stop rerunning the suite.", "I'll not cease rerunning the suite.",
                        "I'll not refrain from rerunning the suite.", "I'll not postpone the rerun.",
                        "I'll not defer the rerun.", "I'll not put off the rerun.",
                        "I'll not hold off on the rerun.", "I'll not avoid the suite.", "I'll not abandon the fix.",
                        "I'll not let the suite stay red.", "I'll do nothing short of a full rerun.",
                        "I'll do nothing aside from the gate.", "I'll do nothing save rerun the suite.",
                        "I'll not do anything except rerun the suite.",
                        "I'll not do anything other than rerun the suite.",
                        "I'll not do anything besides push the branch.",
                        "I'll not run anything apart from the suite.",
                        "I'll not make any change beyond rerunning the suite.",
                        "I'll not take long to rerun the suite.",
                        "I'll do no fewer than three runs.", "I'll do nothing working on it now.",
                        "I'm starting no lane for it. Then I'll merge the branch.",
                        "I'm starting no lane for it, and I'll run the suite.",
                        "I'll start no lane and run the suite.", "I'll take no shortcuts and fix the bug.",
                        "I'll touch nothing else and push the branch.",
                        "I'll make no changes to the gate and run the suite.",
                        "I'll start no lane and run tests.", "I'll start no lane and will run the suite.",
                        "I'll start no lane and also run the suite.", "I'll make no changes and push.",
                        "I'll start no lane, then run the suite.", "I'll start no lane but run the suite.",
                        "I'll start no lane; run the suite.", "I'll start no lane, instead run the suite.",
                        "I'll start no lane \N{EM DASH} run the suite.", "I'll start no lane, just run the suite.",
                        "I'll start no lane, only run the suite.", "I'll start no lane or run the suite.",
                        "I'll start no lane so run the suite.", "I'll start no lane while I run the suite.",
                        "I'll start no lane before I run the suite.",
                        "I'll start no lane, run the suite.", "I'll start no lane, rerun CI.",
                        "I'll start no lane: run the suite.", "I'll start no lane \N{EN DASH} run the suite.",
                        "I'll start no lane -- run the suite."):
            with self.subTest(message=message):
                self.assert_blocks(message)

    def test_subagent_stop_passes(self):
        self.assert_passes("Next I'll look at the reviewer nits.", event="SubagentStop")


if __name__ == "__main__":
    unittest.main()
