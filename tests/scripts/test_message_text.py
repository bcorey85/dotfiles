"""Checks for message_text.without_draft_blocks: fenced blocks and blockquote lines are dropped, every other line
stays."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
from message_text import without_draft_blocks


class WithoutDraftBlocksTest(unittest.TestCase):
    def test_drops_draft_lines_and_keeps_the_rest(self):
        cases = (
            ("backtick fence", "Before\n```\ninside\n```\nAfter", "Before\nAfter"),
            ("tilde fence", "Before\n~~~text\ninside\n~~~\nAfter", "Before\nAfter"),
            ("unclosed fence runs to the end", "Before\n```\ninside\nmore", "Before"),
            ("longer fence is not closed by a shorter one",
             "Before\n````\ninside\n```\nstill inside\n````\nAfter", "Before\nAfter"),
            ("blockquote lines", "Before\n> quoted\n  > indented quote\nAfter", "Before\nAfter"),
            ("plain text is unchanged", "One line.\nTwo lines.", "One line.\nTwo lines."),
            ("greater-than inside a line stays", "a > b", "a > b"),
        )
        for label, text, expected in cases:
            with self.subTest(label):
                self.assertEqual(without_draft_blocks(text), expected, label)


if __name__ == "__main__":
    unittest.main()
