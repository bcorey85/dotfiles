"""Checks that the scripted review loop records one finding and one ask when a later round raises the same file, line
and class again. The harness is the one of test_review_loop_script.py: a stand-in `claude` answers each call from a
canned scenario."""
import unittest

import test_review_loop_script as loop_tests

SECOND_FIX = "limit = 1\nlimit = 21\nlimit = 3\nlimit = 4\nlimit = 5\n"
FIRST_ASK = "`app.py:3` [design-decision] should the limit be configurable per tenant?"
SECOND_ASK = "`app.py:3` [design-decision] is a per-tenant setting for the limit wanted?"


def review_of(fix, ask):
    return f"## Fix\n- {fix}\n\n## Ask\n- {ask}\n\n## Nit\nNone\n"


class RepeatedFindingTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def run_rounds(self, first_review, second_review):
        scenario = {
            "code-reviewer": [{"result": first_review}, {"result": second_review}, {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_tests.APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"app.py": SECOND_FIX}}],
            "closure": [{"result": loop_tests.CLOSED}],
        }
        completed = self.run_script(scenario)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return self.stored_packet()[1]

    def test_a_fix_raised_again_on_the_same_file_line_and_class_is_fixed_once(self):
        first = review_of("`app.py:2` [bug] the limit is wrong for `limit`", "None")
        second = review_of("`app.py:2` [bug] value `limit` is still off on this line", "None")

        packet = self.run_rounds(first, second)

        self.assertEqual([entry["file_line"] for entry in packet["fixed"]], ["app.py:2"])

    def test_an_ask_raised_again_on_the_same_file_line_and_class_is_filed_once(self):
        first = review_of("`app.py:2` [bug] the limit is wrong for `limit`", FIRST_ASK)
        second = review_of("`app.py:4` [bug] the limit is wrong for `other`", SECOND_ASK)

        packet = self.run_rounds(first, second)

        self.assertEqual([entry["file_line"] for entry in packet["ask"]], ["app.py:3"])

    def test_two_findings_on_different_lines_stay_two(self):
        first = review_of("`app.py:2` [bug] the limit is wrong for `limit`", "None")
        second = review_of("`app.py:4` [bug] the cap is wrong for `cap`", "None")

        packet = self.run_rounds(first, second)

        self.assertEqual(sorted(entry["file_line"] for entry in packet["fixed"]), ["app.py:2", "app.py:4"])


if __name__ == "__main__":
    unittest.main()
