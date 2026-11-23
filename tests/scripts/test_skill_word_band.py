"""skill_word_band.py: the total of the words in the named files against a limit."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import START_LOAD_FILES

# The start-load limit AC15 names; change it only with that criterion.
START_LOAD_LIMIT = 3488
DEFAULT_SCRIPT = pathlib.Path(__file__).resolve().parent / "skill_word_band.py"
SCRIPT = pathlib.Path(os.environ.get("SKILL_WORD_BAND_SCRIPT") or DEFAULT_SCRIPT)


def run_band(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False)


class SkillWordBandTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.first = pathlib.Path(self.folder.name) / "first.md"
        self.second = pathlib.Path(self.folder.name) / "second.md"
        self.first.write_text("one two three\nfour\n")
        self.second.write_text("five six\n")

    def test_total_against_the_limit_under_at_and_above(self):
        cases = ((7, 0, "under"), (6, 0, "at"), (5, 1, "above"))
        for limit, expected_exit, label in cases:
            with self.subTest(case=label):
                result = run_band(str(limit), str(self.first), str(self.second))
                self.assertEqual(result.returncode, expected_exit, f"{label}: {result.stderr}")
                lines = result.stdout.splitlines()
                self.assertEqual(lines[0], f"4 {self.first}")
                self.assertEqual(lines[1], f"2 {self.second}")
                self.assertEqual(lines[2], f"6 total (limit {limit})")

    def test_a_bare_list_marker_is_not_a_word(self):
        marked = pathlib.Path(self.folder.name) / "marked.md"
        marked.write_text("- one\n* two\n+ three\n1. four\n12. five\n-six\n1.5 seven\n- \n")
        result = run_band("100", str(marked))
        self.assertEqual(result.stdout.splitlines()[0], f"8 {marked}")

    def test_the_four_start_load_files_are_within_the_limit(self):
        result = run_band(str(START_LOAD_LIMIT), *[str(start_file) for start_file in START_LOAD_FILES])
        self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")

    def test_a_missing_file_exits_2_and_names_it(self):
        missing = pathlib.Path(self.folder.name) / "absent.md"
        result = run_band("10", str(self.first), str(missing))
        self.assertEqual(result.returncode, 2)
        self.assertIn(str(missing), result.stderr)

    def test_a_limit_that_is_not_an_integer_exits_2_and_names_it(self):
        result = run_band("many", str(self.first))
        self.assertEqual(result.returncode, 2)
        self.assertIn("'many'", result.stderr)

    def test_no_file_named_exits_2(self):
        result = run_band("10")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
