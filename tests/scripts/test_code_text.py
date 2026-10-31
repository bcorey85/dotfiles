"""Checks for lib/code_text.py helpers."""
import re
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from code_text import sub_outside_strings

COMMA_NEWLINE = re.compile(r",\n")


class SubOutsideStringsTest(unittest.TestCase):
    def test_match_in_code_is_replaced_and_match_in_a_string_is_kept(self):
        cases = {
            "code": ("f(a,\nb)", "f(a; b)"),
            "triple-quoted string": ('f("""a,\nb""", c,\nd)', 'f("""a,\nb""", c; d)'),
            "triple single quotes": ("f('''a,\nb''')", "f('''a,\nb''')"),
            "escaped quote before a triple-quoted string": ('f("a\\"b", """x,\ny""")', 'f("a\\"b", """x,\ny""")'),
        }
        for shape, (text, expected) in cases.items():
            with self.subTest(shape=shape):
                self.assertEqual(sub_outside_strings(COMMA_NEWLINE, "; ", text), expected)


if __name__ == "__main__":
    unittest.main()
