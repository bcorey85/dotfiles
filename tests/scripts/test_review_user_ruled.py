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
        self.assertIs(ask["user_ruled"], True)

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


class DropPacketUserRuledMarksTest(unittest.TestCase):
    def test_a_mark_the_packet_carries_is_dropped_and_the_ask_kept(self):
        packet = {"ask": [{**REAL_ASK, "user_ruled": True}, dict(REAL_ASK)]}
        review_user_ruled.drop_packet_user_ruled_marks(packet)
        self.assertEqual(packet["ask"], [REAL_ASK, REAL_ASK])

    def test_a_packet_with_no_ask_key_is_left_alone(self):
        packet = {}
        review_user_ruled.drop_packet_user_ruled_marks(packet)
        self.assertEqual(packet, {})


class SkippedBecomeAsksTest(unittest.TestCase):
    def test_given_skips_join_the_existing_asks_after_them(self):
        packet = {"ask": [REAL_ASK], "skipped_fp": [given("one", file_line="a.py:1"), given("two", file_line="b.py:2")]}
        review_user_ruled.skipped_become_asks(packet, ["one", "two"])
        self.assertEqual(len(packet["ask"]), 3)
        self.assertEqual(packet["ask"][0], REAL_ASK)
        self.assertEqual([ask["file_line"] for ask in packet["ask"][1:]], ["a.py:1", "b.py:2"])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_skip_not_given_by_the_caller_stays_a_skip(self):
        reviewer_skip = {"item": "c.py:3 three", "reason": "round two", "file_line": "c.py:3", "class": "other"}
        packet = {"ask": [], "skipped_fp": [given("a.py:1 one"), reviewer_skip]}
        review_user_ruled.skipped_become_asks(packet, ["a.py:1 one", "c.py:3 three"])
        self.assertEqual(len(packet["ask"]), 1)
        self.assertEqual(packet["skipped_fp"], [reviewer_skip])

    def test_only_a_skip_of_a_finding_the_user_ruled_on_becomes_an_ask(self):
        session_ruled = given("a.py:1 one", file_line="a.py:1")
        user_ruled = given("b.py:2 two", file_line="b.py:2")
        packet = {"ask": [], "skipped_fp": [session_ruled, user_ruled]}
        review_user_ruled.skipped_become_asks(packet, ["b.py:2 two"])
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["b.py:2"])
        self.assertEqual(packet["skipped_fp"], [session_ruled])

    def test_skips_with_the_same_text_as_a_user_ruled_finding_all_become_asks(self):
        # A skip names its finding by text alone, so two findings with one text cannot be told apart.
        twins = [given("a.py:1 one"), given("a.py:1 one")]
        packet = {"ask": [], "skipped_fp": twins}
        review_user_ruled.skipped_become_asks(packet, ["a.py:1 one"])
        self.assertEqual(len(packet["ask"]), 2)
        self.assertEqual(packet["skipped_fp"], [])

    def test_no_user_ruled_finding_leaves_every_skip_in_place(self):
        packet = {"ask": [], "skipped_fp": [given("a.py:1 one")]}
        review_user_ruled.skipped_become_asks(packet, [])
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["skipped_fp"]), 1)


if __name__ == "__main__":
    unittest.main()
