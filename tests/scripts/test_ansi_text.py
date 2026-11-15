import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import ansi_text


class StripAnsiTest(unittest.TestCase):
    def test_colour_and_bold_codes_are_removed(self):
        text = "\x1b[1m\x1b[32m2 passed\x1b[39m\x1b[22m (2)"

        self.assertEqual("2 passed (2)", ansi_text.strip_ansi(text))

    def test_a_cursor_code_is_removed(self):
        self.assertEqual("done", ansi_text.strip_ansi("\x1b[2K\x1b[1Gdone"))

    def test_colon_parameters_and_private_mode_codes_are_removed(self):
        for text in ("\x1b[38:2::255:0:0mred\x1b[0m", "\x1b[>4;2mred"):
            with self.subTest(text=text):
                self.assertEqual("red", ansi_text.strip_ansi(text))

    def test_plain_text_is_unchanged(self):
        self.assertEqual("Ran 7 tests [ok]", ansi_text.strip_ansi("Ran 7 tests [ok]"))
