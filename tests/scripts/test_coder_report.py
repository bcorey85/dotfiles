"""Tests for coder_report.py: reading a coder hand-back report."""
import importlib.util
import unittest

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("coder_report", toolkit_paths.CODE_DIR / "coder_report.py")
coder_report = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(coder_report)


class OpenQuestionsTest(unittest.TestCase):
    def test_a_json_list_gives_its_strings(self):
        self.assertEqual(coder_report.open_questions('OPEN QUESTIONS: ["a?", "b?"]'), ["a?", "b?"])

    def test_none_and_a_missing_line_give_no_questions(self):
        self.assertEqual(coder_report.open_questions("OPEN QUESTIONS: none"), [])
        self.assertEqual(coder_report.open_questions("BEHAVIOR: none"), [])

    def test_an_unreadable_value_comes_back_as_one_flagged_item(self):
        questions = coder_report.open_questions("OPEN QUESTIONS: what about x")

        self.assertEqual(len(questions), 1)
        self.assertIn("could not be read as a JSON list of strings: what about x", questions[0])


class ImpactBlockTest(unittest.TestCase):
    REPORT = "Done.\nPLAN-IMPACT:\n  assumed: a\n  found: b\n"

    def test_the_header_and_its_indented_lines_make_the_block(self):
        self.assertEqual(coder_report.plan_impact_block(self.REPORT), "PLAN-IMPACT:\n  assumed: a\n  found: b")
        self.assertTrue(coder_report.has_plan_impact_block(self.REPORT))

    def test_unindented_key_lines_and_a_bold_header_still_make_the_block(self):
        report = "**PLAN-IMPACT:**\nassumed: a\ncause: c\n"

        self.assertEqual(coder_report.plan_impact_block(report), "PLAN-IMPACT:\n  assumed: a\n  cause: c")

    def test_a_yes_line_with_no_block_gives_the_fallback_that_is_not_a_found_block(self):
        report = "PLAN-IMPACT: yes\n"

        self.assertIn("block not found", coder_report.plan_impact_block(report))
        self.assertFalse(coder_report.has_plan_impact_block(report))

    def test_no_marker_gives_none(self):
        self.assertIsNone(coder_report.plan_impact_block("All done."))


class MarkerLinesTest(unittest.TestCase):
    def test_only_the_marker_line_recommends_eng_spec(self):
        self.assertTrue(coder_report.recommends_eng_spec("x\n**RECOMMEND: /eng-spec**\n"))
        self.assertFalse(coder_report.recommends_eng_spec("I recommend /eng-spec for this."))

    def test_why_lines_group_by_file(self):
        report = "WHY: `a.py` 1-5 — first\nWHY: a.py:7-9 - second\nWHY: b.py 2-3 — third\n"

        self.assertEqual(coder_report.why_by_file(report), {
            "a.py": [{"lines": "1-5", "note": "first"}, {"lines": "7-9", "note": "second"}],
            "b.py": [{"lines": "2-3", "note": "third"}]})

    def test_behavior_lines_drop_none(self):
        self.assertEqual(coder_report.behavior_lines("BEHAVIOR: adds x\nBEHAVIOR: none\n"), ["adds x"])


if __name__ == "__main__":
    unittest.main()
