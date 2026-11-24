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

    def run_gate(self, message, event="Stop", stop_hook_active=False):
        payload = {"hook_event_name": event, "cwd": str(self.tmp), "last_assistant_message": message,
                   "stop_hook_active": stop_hook_active, "transcript_path": ""}
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, cwd=str(self.tmp), env=environment)
        self.assertEqual((finished.returncode, finished.stderr), (0, ""))
        return finished.stdout

    def assert_blocks(self, message):
        output = self.run_gate(message)
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

    def test_subagent_stop_passes(self):
        self.assert_passes("Next I'll look at the reviewer nits.", event="SubagentStop")


if __name__ == "__main__":
    unittest.main()
