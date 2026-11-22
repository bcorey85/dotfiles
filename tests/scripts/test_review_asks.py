import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_asks
import review_fix_asks


class IsConditionalChangeTest(unittest.TestCase):
    def test_a_change_that_depends_on_a_missing_answer_is_conditional(self):
        conditional = [
            "If not confirmed, revert X",
            "  unless the user objects, drop the cache",
            "Otherwise remove the retry",
            "Revert X if not confirmed",
            "Keep the guard; remove it if the user confirms",
            "Keep X if yes",
            "Remove it if no, keep it",
            "If the user agrees, drop the column",
            "If not accepted, keep X",
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
            "Show the banner if the user is an admin",
            "Return 202 if accepted by the queue",
            "if accepted, return `[]` when the list is empty",
            "if accepted as a cut, build `COMMIT` and `GIT_THEN_COMMIT` from `commit\\b(?!-)` again and leave "
            "`COMMITTING_CALL` only in `UNREADABLE_GIT_THEN_COMMIT`.",
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


class ReadOutcomesTest(unittest.TestCase):
    def test_an_unknown_outcome_word_error_says_rejected_is_the_leave_it_outcome(self):
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            review_fix_asks.read_outcomes(["leave-it"], [{}])
        message = str(raised.exception)
        self.assertIn(f"{review_asks.REJECTED}: {review_asks.REJECT_MEANS}", message)
        self.assertIn(f"{review_asks.ACCEPTED}: {review_asks.ACCEPT_MEANS}", message)
        self.assertIn("'leave it'", message)


if __name__ == "__main__":
    unittest.main()


class NumberedAskLinesTest(unittest.TestCase):
    ASKS = (
        {"question": "Cap at 3?", "gate": "code-reviewer", "class": "smell", "file_line": "a.py:1"},
        {"question": "Drop it?", "gate": "code-reviewer", "class": "docs", "user_only": True},
    )

    def test_each_ask_line_opens_with_the_marker_and_its_number(self):
        lines = review_asks.numbered_ask_lines(list(self.ASKS))

        self.assertEqual(f"{review_asks.ASK_MARKER} 1. Cap at 3?", lines[0])
        self.assertTrue(lines[1].startswith(f"{review_asks.ASK_MARKER} 2. "))

    def test_the_detail_line_opens_with_the_marker_and_keeps_the_location_and_class(self):
        lines = review_asks.numbered_ask_lines(list(self.ASKS), detail=True)

        self.assertEqual(f"{review_asks.ASK_MARKER} 1. a.py:1  [code-reviewer/smell]", lines[0])
        self.assertIn("no file:line  [code-reviewer/docs]", lines[2])

    def test_no_script_parses_the_line_back_so_the_old_form_in_a_saved_packet_loads(self):
        old_packet_ask = {"question": "Cap at 3?", "gate": "code-reviewer", "class": "smell", "file_line": "a.py:1",
                          "finding_id": "abc"}

        lines = review_asks.numbered_ask_lines([old_packet_ask], detail=True)

        self.assertTrue(lines[0].endswith("1. a.py:1  [code-reviewer/smell]"))
