import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_fix_asks
import ruled_change_text
from no_code_notes import NO_CODE_NOTES


class RuledNoteTest(unittest.TestCase):
    def test_a_no_code_note_is_read_back_from_the_text_the_builder_made(self):
        for note in NO_CODE_NOTES:
            with self.subTest(note):
                text = ruled_change_text.changed_text("a.py:1 base", note, ruled_change_text.USER_CLAUSE)
                self.assertEqual(ruled_change_text.ruled_note(text), note)
                self.assertTrue(ruled_change_text.is_no_code_ruling(note))
                self.assertTrue(ruled_change_text.is_no_code_finding(text))

    def test_a_note_is_read_behind_every_clause(self):
        clauses = (ruled_change_text.USER_CLAUSE, ruled_change_text.SESSION_CLAUSE, ruled_change_text.UNNAMED_CLAUSE)
        for clause in clauses:
            with self.subTest(clause):
                text = ruled_change_text.changed_text("b", "n", clause)
                self.assertEqual(ruled_change_text.ruled_note(text), "n")

    def test_the_latest_ruling_wins_over_an_earlier_one(self):
        first = ruled_change_text.changed_text("a.py:1 base", "Make no code change.", ruled_change_text.USER_CLAUSE)
        second = ruled_change_text.changed_text(first, "add a guard", ruled_change_text.SESSION_CLAUSE)
        self.assertEqual(ruled_change_text.ruled_note(second), "add a guard")
        self.assertFalse(ruled_change_text.is_no_code_finding(second))

    def test_other_notes_and_unruled_text_are_not_no_code(self):
        self.assertFalse(ruled_change_text.is_no_code_ruling("add a guard in parse()"))
        self.assertIsNone(ruled_change_text.ruled_note("a.py:1 Proposed change: no code change"))
        self.assertFalse(ruled_change_text.is_no_code_finding("a.py:1 Proposed change: no code change"))

    def test_a_no_code_note_that_asks_for_a_test_edit_is_a_change(self):
        notes = (
            "no code change; add a case to the test loop and pin the output",
            "No code change. Update the fixture for the new output.",
            "no code change; extend the tests to cover the empty list",
            "no code change, add a test case for it",
            "no code change - add a test",
            "no code change — add a test",
            "no code change \N{EN DASH} add a test",
            "no code change\N{EM DASH}add a test",
            "no code change\N{EN DASH}add a test",
            "no code change -- add a test",
            "no code change--add a test",
            "no code change; update test_ruled_change_text.py to pin the output",
            "no code change, but add a test",
            "no code change, but also add a test",
            "no code change and then add a test",
            "no code change and add a test case",
            "no code change; also add a test",
            "no code change; then update the fixture",
            "no code change, please add a test",
            "no code change, just add a test",
            "no code change; instead add a test",
            "no code change; write a test for it",
            "no code change; update conftest.py:12 to add a fixture",
            "no code change; update foo() to cover the empty case",
            "no code change; now create a fixture",
            "no code change, so include a test case",
            "no code change; still adjust the test",
            "no code change; fix the test",
            "no code change; update conftest.py to add a fixture",
            "no code change; update helpers.py to cover the empty case",
        )
        for note in notes:
            with self.subTest(note):
                self.assertFalse(ruled_change_text.is_no_code_ruling(note))
                text = ruled_change_text.changed_text("a.py:1 base", note, ruled_change_text.USER_CLAUSE)
                self.assertFalse(ruled_change_text.is_no_code_finding(text))

    def test_a_plain_no_code_note_stays_no_code(self):
        notes = (
            "no code change",
            "no code change; the current text is right",
            "no code change; add no new test case",
            "no code change; change nothing, the test is right",
            "no code change, but add no test",
            "no code change, but also add no test",
            "no code change; add a guard",
            "no code change; update the parser",
            "no code change; add none of the new test cases",
            "no code change; do not add a test",
            "no code change; fix not the test but the docs",
            "no code change; change nothing about the test",
        )
        for note in notes:
            with self.subTest(note):
                self.assertTrue(ruled_change_text.is_no_code_ruling(note))
                text = ruled_change_text.changed_text("a.py:1 base", note, ruled_change_text.USER_CLAUSE)
                self.assertTrue(ruled_change_text.is_no_code_finding(text))

    def test_ask_finding_text_carries_the_note_in_both_forms(self):
        ask = {"question": "q", "file_line": "a.py:1", "class": "bug", "change": "add X"}
        converted = {**ask, "user_ruled": True}
        for item in (ask, converted):
            text = review_fix_asks.ask_finding_text(item, "Make no code change.")
            self.assertTrue(ruled_change_text.is_no_code_finding(text), text)

    def test_a_no_code_note_is_read_for_every_ruler(self):
        ask = {"question": "q", "file_line": "a.py:1", "class": "bug", "change": "add X"}
        for decided_by in ("user", "session", None):
            with self.subTest(decided_by):
                text = review_fix_asks.ask_finding_text(ask, "Make no code change.", decided_by)
                self.assertEqual(ruled_change_text.ruled_note(text), "Make no code change.")
                self.assertTrue(ruled_change_text.is_no_code_finding(text), text)
                clause = review_fix_asks.ruler_clause(decided_by)
                self.assertTrue(text.endswith(f"{clause}{ruled_change_text.PLACE_MARKER}Make no code change."), text)


if __name__ == "__main__":
    unittest.main()
