import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_asks


class IsConditionalChangeTest(unittest.TestCase):
    def test_a_change_that_depends_on_a_missing_answer_is_conditional(self):
        conditional = [
            "If not confirmed, revert X",
            "  unless the user objects, drop the cache",
            "Otherwise remove the retry",
            "Revert X if not confirmed",
            "Keep X if yes",
            "Remove it if no, keep it",
            "If the user agrees, drop the column",
            "Keep the guard; remove it if the user confirms",
        ]
        for change in conditional:
            with self.subTest(change):
                self.assertTrue(review_asks.is_conditional_change(change))

    def test_a_plain_change_is_not_conditional(self):
        plain = [
            "cap retries at 3",
            "add an index on tenant_id",
            "Revert X",
            "Notify the user, then restore -j8",
            "whenever it runs, log the count",
            "When the list is empty, return []",
            "raise ValueError if not found",
            "When the flag is unset, restore -j8",
            "If no-op, skip",
            "Keep the loop if no caller depends on it",
            "",
        ]
        for change in plain:
            with self.subTest(change):
                self.assertFalse(review_asks.is_conditional_change(change))


class AcceptRejectLinesTest(unittest.TestCase):
    def test_a_change_that_ends_in_a_question_or_exclamation_mark_gets_no_period(self):
        for change in ("Revert X?", "Revert X!"):
            with self.subTest(change):
                self.assertEqual(
                    review_asks.accept_reject_lines(change),
                    [f"   Accept = make this change: {change} Reject = leave the code as it is."])

    def test_trailing_dots_collapse_to_one_period(self):
        self.assertEqual(
            review_asks.accept_reject_lines("Wait..."),
            ["   Accept = make this change: Wait. Reject = leave the code as it is."])

    def test_a_change_that_ends_in_a_period_gets_one_period_before_reject(self):
        for change in ("Revert X", "Revert X.", "Revert X. "):
            with self.subTest(change):
                self.assertEqual(
                    review_asks.accept_reject_lines(change),
                    ["   Accept = make this change: Revert X. Reject = leave the code as it is."])


if __name__ == "__main__":
    unittest.main()
