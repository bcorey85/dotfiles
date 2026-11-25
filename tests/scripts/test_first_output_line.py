"""scripts/.local/lib/first_output_line.py: the first line of a command's output."""
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / ".local" / "lib"))
import first_output_line  # noqa: E402


class FirstOutputLineTest(unittest.TestCase):
    def test_the_first_line_of_the_stripped_text_is_returned(self):
        cases = {
            "one line": ("fatal: bad\n", "fatal: bad"),
            "leading blank lines": ("\n\n  fatal: bad\nsecond\n", "fatal: bad"),
            "empty text": ("", "no output"),
            "blank text": ("  \n\n", "no output"),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(first_output_line.first_output_line(text), expected)


if __name__ == "__main__":
    unittest.main()
