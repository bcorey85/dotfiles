"""Checks that the scripted review loop keeps the tests the plan's scoped commands run by name through a fix pass.

The harness is the one of test_review_loop_script.py: a stand-in `claude` answers each call from a canned scenario."""
import unittest

import test_review_loop_script as loop_tests
from test_named_test_targets import TARGET, TEST_FILE, WITH_NAMED_TEST, WITHOUT_NAMED_TEST

GATE_COMMAND = f"python3 -m pytest {TARGET}"
RESTORE_TEXT = f"restore {TARGET}: the last fix pass removed a test the plan runs by name"


class NamedTestsLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        (self.repo / "tests").mkdir()
        self.commit_files({TEST_FILE: WITH_NAMED_TEST})
        self.gate_commands = [GATE_COMMAND]

    def run_with_coders(self, *coders):
        scenario = {
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW}],
            "coder": list(coders),
            "closure": [{"result": loop_tests.CLOSED}],
        }
        completed = self.run_script(scenario)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]

    def test_the_coder_prompt_lists_the_tests_the_plan_runs_by_name(self):
        coder_prompts = self.run_with_coders({"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}})

        self.assertIn(f"Tests the plan runs by name; never delete or rename them: {TARGET}", coder_prompts[0])

    def test_a_fix_pass_that_deletes_a_plan_named_test_gets_one_restore_pass(self):
        deleting = {"result": "Fixed 1.",
                    "edits": {"app.py": loop_tests.APP_FIXED, TEST_FILE: WITHOUT_NAMED_TEST}}
        restoring = {"result": "Restored.\nSKIPPED 1: needs the user", "edits": {TEST_FILE: WITH_NAMED_TEST}}

        coder_prompts = self.run_with_coders(deleting, restoring)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn(RESTORE_TEXT, coder_prompts[1])
        # The restore pass's skip line is not the fix pass's report, so issue 1 stays fixed.
        self.assertEqual([row["actioned"] for row in self.finding_rows() if row["iter"] == "1"], ["fixed"])
        _row, packet = self.stored_packet()
        self.assertNotIn("removed plan-named test", " ".join(packet["blockers"]))

    def test_a_fix_pass_that_renames_a_plan_named_test_gets_one_restore_pass(self):
        renaming = {"result": "Fixed 1.",
                    "edits": {"app.py": loop_tests.APP_FIXED,
                              TEST_FILE: WITH_NAMED_TEST.replace("test_limit", "test_limit_new")}}
        restoring = {"result": "Restored.\nSKIPPED 1: needs the user", "edits": {TEST_FILE: WITH_NAMED_TEST}}

        coder_prompts = self.run_with_coders(renaming, restoring)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn(RESTORE_TEXT, coder_prompts[1])

    def test_a_second_deletion_stops_with_the_named_test_blocker_not_a_scoped_test_failure(self):
        deleting = {"result": "Fixed 1.",
                    "edits": {"app.py": loop_tests.APP_FIXED, TEST_FILE: WITHOUT_NAMED_TEST}}
        still_deleted = {"result": "Done.", "edits": {TEST_FILE: WITHOUT_NAMED_TEST}}

        coder_prompts = self.run_with_coders(deleting, still_deleted)

        self.assertEqual(len(coder_prompts), 2)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(f"the fix pass removed plan-named test {TARGET}", packet["blockers"][0])
        self.assertNotIn("failed:", packet["scoped_tests"])

    def test_a_failed_restore_pass_still_records_the_files_the_first_pass_edited(self):
        deleting = {"result": "Fixed 1.",
                    "edits": {"app.py": loop_tests.APP_FIXED, TEST_FILE: WITHOUT_NAMED_TEST}}
        scenario = {
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [deleting, {"result": "Prompt is too long", "exit": 1}],
            "closure": [{"result": loop_tests.CLOSED}],
        }

        completed = self.run_script(scenario)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertIn("app.py", packet["files_touched"])


if __name__ == "__main__":
    unittest.main()
