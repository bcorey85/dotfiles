import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_user_ruled

REAL_ASK = {"question": "keep the retry?", "file_line": "src/retry.ts:10", "class": "bug", "gate": "none"}


def given(item, **fields):
    return {"item": item, "reason": "coder reason", "file_line": "x.py:1", "class": "other", "given": True, **fields}


class SkippedEntryAsAskTest(unittest.TestCase):
    def test_an_ask_takes_its_location_class_and_proposed_change_from_the_entry_fields(self):
        entry = {"item": "the greeting is wrong", "reason": "a fixture", "file_line": "README.md:1", "class": "bug"}
        ask = review_user_ruled.skipped_entry_as_ask(entry)
        self.assertEqual(ask["file_line"], "README.md:1")
        self.assertEqual(ask["class"], "bug")
        self.assertEqual(ask["change"], "the greeting is wrong")

    def test_an_unclassed_unlocated_entry_asks_with_the_default_class_and_one_line_text(self):
        entry = {"item": "plain\ntext", "reason": "two\nlines", "file_line": "unlocated", "class": None}
        ask = review_user_ruled.skipped_entry_as_ask(entry)
        self.assertEqual(ask["class"], "other")
        self.assertEqual(ask["file_line"], review_user_ruled.handback.UNLOCATED)
        self.assertEqual(ask["change"], "plain text")
        self.assertIn("two lines", ask["question"])
        self.assertNotIn("\n", ask["question"])

    def test_a_reason_ending_in_sentence_punctuation_leaves_one_terminal_mark(self):
        for ending in [".", "?", "!", ":", ";", " ?"]:
            entry = {"item": "x", "reason": f"not needed{ending}", "file_line": "x.py:1", "class": "other"}
            ask = review_user_ruled.skipped_entry_as_ask(entry)
            self.assertIn("not needed. Apply it anyway?", ask["question"], f"ending {ending!r}")


class SkippedBecomeAsksTest(unittest.TestCase):
    def test_given_skips_join_the_existing_asks_after_them(self):
        packet = {"ask": [REAL_ASK], "skipped_fp": [given("one", file_line="a.py:1"), given("two", file_line="b.py:2")]}
        review_user_ruled.skipped_become_asks(packet)
        self.assertEqual(len(packet["ask"]), 3)
        self.assertEqual(packet["ask"][0], REAL_ASK)
        self.assertEqual([ask["file_line"] for ask in packet["ask"][1:]], ["a.py:1", "b.py:2"])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_skip_not_given_by_the_caller_stays_a_skip(self):
        reviewer_skip = {"item": "c.py:3 three", "reason": "round two", "file_line": "c.py:3", "class": "other"}
        packet = {"ask": [], "skipped_fp": [given("a.py:1 one"), reviewer_skip]}
        review_user_ruled.skipped_become_asks(packet)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertEqual(packet["skipped_fp"], [reviewer_skip])


if __name__ == "__main__":
    unittest.main()
