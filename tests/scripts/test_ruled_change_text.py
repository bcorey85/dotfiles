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
                text = ruled_change_text.changed_text("a.py:1 base", note)
                self.assertEqual(ruled_change_text.ruled_note(text), note)
                self.assertTrue(ruled_change_text.is_no_code_ruling(note))
                self.assertTrue(ruled_change_text.is_no_code_finding(text))

    def test_other_notes_and_unruled_text_are_not_no_code(self):
        self.assertFalse(ruled_change_text.is_no_code_ruling("add a guard in parse()"))
        self.assertIsNone(ruled_change_text.ruled_note("a.py:1 Proposed change: no code change"))
        self.assertFalse(ruled_change_text.is_no_code_finding("a.py:1 Proposed change: no code change"))

    def test_ask_finding_text_carries_the_note_in_both_forms(self):
        ask = {"question": "q", "file_line": "a.py:1", "class": "bug", "change": "add X"}
        converted = {**ask, "user_ruled": True}
        for item in (ask, converted):
            text = review_fix_asks.ask_finding_text(item, "Make no code change.")
            self.assertTrue(ruled_change_text.is_no_code_finding(text), text)


if __name__ == "__main__":
    unittest.main()
