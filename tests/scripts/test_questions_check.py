import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("QUESTIONS_CHECK_SCRIPT") or TOOLS_DIR / "questions_check.py")

CLEAN = """# Research Questions

1. How does the queue system work? Trace the data flow from `add` to `pop`.
2. What types exist for a queue item, and where are they defined?

3. What test patterns exist for the queue? Where are the test files?

## Exploration Map

- `bin/` — queue commands
"""


class QuestionsCheckTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.questions_file = pathlib.Path(temp.name) / "01-questions.md"

    def check(self, text):
        self.questions_file.write_text(text)
        return subprocess.run([sys.executable, str(SCRIPT), "check", str(self.questions_file)],
                              capture_output=True, text=True)

    def assert_fails_with(self, text, expected):
        finished = self.check(text)
        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn(expected, finished.stdout)

    def test_a_clean_file_passes(self):
        finished = self.check(CLEAN)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_a_named_heading_passes(self):
        self.assertEqual(self.check(CLEAN.replace("# Research", "# LS-1 Research")).returncode, 0)

    def test_a_clause_deleted_in_place_fails(self):
        for cut in ("does the plan reference, and ?", "is read, or?", "is it set ,?", "where is it ?"):
            with self.subTest(cut=cut):
                text = CLEAN.replace("and where are they defined?", cut)
                self.assert_fails_with(text, "line 4: a clause ends cut short before `?`")

    def test_two_questions_on_one_line_fail(self):
        merged = CLEAN.replace("defined?\n\n3.", "defined?3.")
        self.assert_fails_with(merged, "line 4: two numbered questions on one line")
        self.assert_fails_with(CLEAN.replace("defined?\n\n3.", "defined? 3."), "two numbered questions on one line")

    def test_a_question_wrapped_onto_a_second_line_fails(self):
        wrapped = CLEAN.replace("and where are they defined?", "and where are they\n   defined?")
        self.assert_fails_with(wrapped, "line 5: expected `3. <question>?` on one line, got: defined?")

    def test_numbering_out_of_order_fails(self):
        self.assert_fails_with(CLEAN.replace("3. What test", "4. What test"), "question numbered 4, expected 3")

    def test_a_line_with_no_question_fails(self):
        text = CLEAN.replace("and where are they defined?", "and their definitions.")
        self.assert_fails_with(text, "line 4: no `?`")

    def test_a_missing_heading_or_empty_list_fails(self):
        self.assert_fails_with("1. What exists?\n", "no `# Research Questions` heading")
        self.assert_fails_with("# Research Questions\n\n## Exploration Map\n", "the question list is empty")

    def test_bad_usage_exits_2(self):
        finished = subprocess.run([sys.executable, str(SCRIPT), "lint"], capture_output=True, text=True)
        self.assertEqual(finished.returncode, 2)


if __name__ == "__main__":
    unittest.main()
