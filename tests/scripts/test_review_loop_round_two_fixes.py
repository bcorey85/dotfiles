"""Checks that the scripted review loop sends every round-two fix finding to the fix coder, wherever its file:line sits
against the previous fix diff and whatever its class. Set REVIEW_LOOP_SCRIPT to run against another copy.

The harness is the one of test_review_loop_script.py: a stand-in `claude` answers each call from a canned scenario."""
import sys
import unittest

import test_review_loop_script as loop_tests
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import capped_review

NOTES_FIXED = "value = {'a': 1, 'b': 2, 'c': 3}\n"
OUTSIDE_DOCS = "`notes.py:1` [docs] the value has no comment"
OUTSIDE_SMELL = "`notes.py:1` [smell] the value name is vague"
OUTSIDE_BUG = "`notes.py:1` [bug] the value drops key c"
NO_LOCATION = "[docs] the plan promise has no test"
NO_CLASS = "`notes.py:1` the value reads oddly"
# A fix of the first round touches app.py only, so notes.py sits outside the fix diff.
FIRST_CODER = {"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}}


def review_of(*fixes):
    lines = "".join(f"- {fix}\n" for fix in fixes)
    return f"## Fix\n{lines}\n## Ask\nNone\n\n## Nit\nNone\n"


class RoundTwoFixesTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def run_two_rounds(self, *second_round_fixes, second_coder=None, header_extra="", first_round=True):
        """Round one files an app.py fix; round two files `second_round_fixes`. Returns the fix coder prompts."""
        reviews = [{"result": review_of(*second_round_fixes)}]
        coders = [second_coder or {"result": "Fixed.", "edits": {"notes.py": NOTES_FIXED}}]
        if first_round:
            reviews.insert(0, {"result": loop_tests.FIX_REVIEW})
            coders.insert(0, FIRST_CODER)
        scenario = {"code-reviewer": reviews, "coder": coders, "closure": [{"result": loop_tests.CLOSED}]}
        completed = self.run_script(scenario, header_extra=header_extra)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return [call["prompt"] for call in self.fake_calls() if call["key"] == "coder"]

    def test_a_round_two_docs_fix_outside_the_fix_diff_reaches_the_coder(self):
        coder_prompts = self.run_two_rounds(OUTSIDE_DOCS)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn("the value has no comment", coder_prompts[1])

    def test_a_round_two_smell_fix_outside_the_fix_diff_reaches_the_coder(self):
        coder_prompts = self.run_two_rounds(OUTSIDE_SMELL)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn("the value name is vague", coder_prompts[1])

    def test_a_round_two_bug_fix_outside_the_fix_diff_reaches_the_coder(self):
        coder_prompts = self.run_two_rounds(OUTSIDE_BUG)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn("the value drops key c", coder_prompts[1])

    def test_a_finding_with_no_file_line_or_no_class_reaches_the_coder(self):
        coder_prompts = self.run_two_rounds(NO_LOCATION, NO_CLASS)

        self.assertEqual(len(coder_prompts), 2)
        self.assertIn("the plan promise has no test", coder_prompts[1])
        self.assertIn("the value reads oddly", coder_prompts[1])

    def test_a_skipped_round_two_fix_is_not_left_remaining_and_no_row_is_logged_none(self):
        # The coder fixes the docs finding and leaves the smell finding with a skip line.
        second_coder = {"result": "Fixed 1.\nSKIPPED 2: the name is the plan's", "edits": {"notes.py": NOTES_FIXED}}

        self.run_two_rounds(OUTSIDE_DOCS, OUTSIDE_SMELL, second_coder=second_coder)

        _row, packet = self.stored_packet()
        self.assertEqual(packet["findings_remaining"], [])
        self.assertIn(OUTSIDE_DOCS, [entry["finding"] for entry in packet["fixed"]])
        # The skipped finding lands in the packet's skipped_fp list, with the coder's skip line as its reason.
        skipped = [(entry["item"], entry["class"]) for entry in packet["skipped_fp"]]
        self.assertEqual(skipped, [(OUTSIDE_SMELL, "smell")])
        self.assertIn("the name is the plan's", packet["skipped_fp"][0]["reason"])
        notes_rows = [row for row in self.finding_rows() if row["path_key"] == "notes.py"]
        self.assertEqual(sorted((row["class"], row["actioned"]) for row in notes_rows),
                         [("docs", "fixed"), ("smell", "skipped_fp")])

    def test_a_round_of_only_outside_fixes_calls_the_coder_and_the_loop_ends_at_its_cap(self):
        self.run_two_rounds(OUTSIDE_DOCS, OUTSIDE_SMELL)

        calls = self.fake_calls()
        reviewer_calls = [call for call in calls if call["key"] == "code-reviewer"]
        coder_calls = [call for call in calls if call["key"] == "coder"]
        self.assertEqual(len(coder_calls), 2)
        # A third review round never starts: the budget is the number of rounds the loop ran.
        self.assertEqual(len(reviewer_calls), 2)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["iter"], 2)
        self.assertNotEqual(packet["status"], capped_review.DEFERRED)

    def test_a_round_two_run_resumed_over_an_old_fix_diff_sends_the_finding_to_the_coder(self):
        # The earlier run left its round-one fix diff in the state folder; the resumed run reads it for the tag only.
        old_out = self.state_dir / "loop-script" / loop_tests.AGENT_ID
        old_out.mkdir(parents=True)
        (old_out / "round1-fix.diff").write_text(
            "--- a/app.py\n+++ b/app.py\n@@ -2,1 +2,1 @@\n-limit = 2\n+limit = 20\n")

        coder_prompts = self.run_two_rounds(OUTSIDE_DOCS, header_extra="iter: 1\n", first_round=False)

        self.assertEqual(len(coder_prompts), 1)
        self.assertIn("the value has no comment", coder_prompts[0])
        _row, packet = self.stored_packet()
        self.assertNotEqual(packet["status"], capped_review.DEFERRED)
        self.assertEqual(packet["findings_remaining"], [])


if __name__ == "__main__":
    unittest.main()
