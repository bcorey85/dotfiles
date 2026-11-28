"""Checks for stop_block.py, which builds the line a Stop hook prints to block."""
import json
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import stop_block


class BlockLineTest(unittest.TestCase):
    def test_no_reason_gives_none(self):
        for reasons in ([], [None, ""]):
            with self.subTest(reasons=reasons):
                self.assertIsNone(stop_block.block_line(reasons, "reply", show_reply=True))

    def test_empty_reasons_are_dropped_and_the_rest_joined_with_one_space(self):
        decision = json.loads(stop_block.block_line(["first.", None, "", "second."], "", show_reply=False))
        self.assertEqual(decision, {"decision": "block", "reason": "first. second."})

    def test_show_reply_false_leaves_out_the_system_message_key(self):
        decision = json.loads(stop_block.block_line(["why"], "a reply", show_reply=False))
        self.assertNotIn("systemMessage", decision)

    def test_an_empty_reply_leaves_out_the_system_message_key(self):
        decision = json.loads(stop_block.block_line(["why"], "", show_reply=True))
        self.assertNotIn("systemMessage", decision)

    def test_a_shown_reply_ends_the_reason_with_the_hidden_reply_note(self):
        decision = json.loads(stop_block.block_line(["why."], "a reply", show_reply=True))
        self.assertEqual(decision["reason"], f"why. {stop_block.HIDDEN_REPLY_NOTE}")

    def test_no_shown_reply_leaves_the_hidden_reply_note_out(self):
        for reply, show_reply in (("a reply", False), ("", True)):
            with self.subTest(reply=reply, show_reply=show_reply):
                decision = json.loads(stop_block.block_line(["why."], reply, show_reply=show_reply))
                self.assertEqual(decision["reason"], "why.")

    def test_a_short_reply_shows_as_label_blank_line_reply(self):
        decision = json.loads(stop_block.block_line(["why"], "a reply", show_reply=True))
        self.assertEqual(decision["systemMessage"], f"{stop_block.REPLY_LABEL}\n\na reply")

    def test_a_reply_over_the_limit_is_cut_to_fit_and_ends_on_the_cut_line(self):
        decision = json.loads(stop_block.block_line(["why"], "x" * 20_000, show_reply=True))
        message = decision["systemMessage"]
        self.assertLessEqual(len(message), stop_block.SYSTEM_MESSAGE_LIMIT)
        self.assertTrue(message.endswith(stop_block.CUT_LINE))
        self.assertTrue(message.startswith(stop_block.REPLY_LABEL))

    def test_a_reply_that_fits_exactly_is_not_cut(self):
        room = stop_block.SYSTEM_MESSAGE_LIMIT - len(f"{stop_block.REPLY_LABEL}\n\n")
        message = stop_block.shown_reply("x" * room)
        self.assertEqual(len(message), stop_block.SYSTEM_MESSAGE_LIMIT)
        self.assertNotIn(stop_block.CUT_LINE, message)

    def test_a_reply_one_character_over_is_cut_to_exactly_the_limit(self):
        room = stop_block.SYSTEM_MESSAGE_LIMIT - len(f"{stop_block.REPLY_LABEL}\n\n")
        message = stop_block.shown_reply("x" * (room + 1))
        self.assertEqual(len(message), stop_block.SYSTEM_MESSAGE_LIMIT)
        self.assertTrue(message.endswith(f"\n{stop_block.CUT_LINE}"))
        self.assertTrue(message.startswith(stop_block.REPLY_LABEL))


if __name__ == "__main__":
    unittest.main()
