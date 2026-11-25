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

    def test_subagent_stop_passes(self):
        self.assert_passes("Next I'll look at the reviewer nits.", event="SubagentStop")


if __name__ == "__main__":
    unittest.main()
