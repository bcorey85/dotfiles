import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_fix_asks
import review_loop_packet
import review_loop_prompts
import review_loop_ruled
import ruled_change_text
import source_paths
from finding_record import parse_finding

NO_CODE_NOTES = [
    "no code change (no session hit it; a reviewer-only case gets no new code); add one Watch line to "
    "docs/changes/notes/2026-11-14-x.md naming that branch",
    "no code change; add one Watch line to the change note",
    "Make no code change: git submodule add stays allowed for a coder, since no session has run it as one.",
    "Make no code change.",
]


def ruled_finding(note, location="`a/b.py:3`"):
    return parse_finding(ruled_change_text.changed_text(f"{location} [bug] Proposed change: add X.", note))


class RuledNoteTest(unittest.TestCase):
    def test_a_no_code_note_is_read_back_from_the_text_the_builder_made(self):
        for note in NO_CODE_NOTES:
            with self.subTest(note):
                text = ruled_change_text.changed_text("a.py:1 base", note)
                self.assertEqual(ruled_change_text.ruled_note(text), note)
                self.assertTrue(ruled_change_text.is_no_code_ruling(note))
                self.assertTrue(ruled_change_text.is_no_code_finding(text))

    def test_other_notes_and_unruled_text_are_not_no_code(self):
        self.assertFalse(ruled_change_text.is_no_code_ruling("add a guard in parse()"))
        self.assertIsNone(ruled_change_text.ruled_note("a.py:1 Proposed change: no code change"))
        self.assertFalse(ruled_change_text.is_no_code_finding("a.py:1 Proposed change: no code change"))

    def test_ask_finding_text_carries_the_note_in_both_forms(self):
        ask = {"question": "q", "file_line": "a.py:1", "class": "bug", "change": "add X"}
        converted = {**ask, "user_ruled": True}
        for item in (ask, converted):
            text = review_fix_asks.ask_finding_text(item, "Make no code change.")
            self.assertTrue(ruled_change_text.is_no_code_finding(text), text)

    def test_code_path_excludes_markdown_and_docs(self):
        self.assertFalse(source_paths.is_code_path("docs/changes/notes/x.md"))
        self.assertFalse(source_paths.is_code_path("README.md"))
        self.assertFalse(source_paths.is_code_path("x/docs/y.py"))
        self.assertTrue(source_paths.is_code_path("a/b.py"))


class Host(review_loop_ruled.RuledFindings):
    def __init__(self):
        self.repo = "/repo"
        self.init_ruled_state()


class NoCodeRulingTest(unittest.TestCase):
    def test_the_coder_prompt_names_the_no_code_issue(self):
        host = Host()
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."), ruled_finding(NO_CODE_NOTES[1])]
        numbers = host.no_code_numbers(findings)
        self.assertEqual(numbers, [2])
        with tempfile.TemporaryDirectory() as folder:
            prompt = review_loop_prompts.coder_prompt(
                "/repo", [item.text for item in findings], [], ["a/b.py"], pathlib.Path(folder),
                no_code_numbers=numbers)
            plain = review_loop_prompts.coder_prompt(
                "/repo", [item.text for item in findings], [], ["a/b.py"], pathlib.Path(folder))
        self.assertIn("Issues ruled no code change: 2.", prompt)
        self.assertIn("SKIPPED <n>", prompt)
        self.assertNotIn("ruled no code change", plain)

    def test_a_code_edit_against_a_no_code_ruling_is_flagged_and_a_doc_edit_is_not(self):
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."), ruled_finding(NO_CODE_NOTES[1])]
        host = Host()
        host.flag_broken_no_code_rulings(findings, ["a/c.py", "docs/changes/notes/x.md"])
        self.assertEqual(host.no_code_broken, [])
        host.flag_broken_no_code_rulings(findings, ["a/b.py", "a/c.py"])
        self.assertEqual(host.no_code_broken, [{"issue": 2, "file": "a/b.py"}])

    def test_any_code_file_breaks_the_ruling_when_every_finding_is_no_code(self):
        host = Host()
        host.flag_broken_no_code_rulings([ruled_finding(NO_CODE_NOTES[3])], ["z/other.py", "docs/n.md"])
        self.assertEqual(host.no_code_broken, [{"issue": 1, "file": "z/other.py"}])

    def test_a_file_that_another_finding_also_names_is_not_flagged(self):
        host = Host()
        findings = [parse_finding("`a/b.py:1` [bug] Proposed change: fix b."), ruled_finding(NO_CODE_NOTES[1])]
        host.flag_broken_no_code_rulings(findings, ["a/b.py"])
        self.assertEqual(host.no_code_broken, [])

    def test_every_no_code_finding_blames_the_issue_that_names_the_file(self):
        host = Host()
        findings = [ruled_finding(NO_CODE_NOTES[1], "`a/c.py:1`"), ruled_finding(NO_CODE_NOTES[3])]
        host.flag_broken_no_code_rulings(findings, ["a/b.py", "z/other.py"])
        self.assertEqual(host.no_code_broken, [{"issue": 2, "file": "a/b.py"}, {"issue": 1, "file": "z/other.py"}])

    def test_a_nit_may_change_code_when_every_finding_is_no_code(self):
        host = Host()
        nit = parse_finding("`z/nit.py:4` [nit] rename x.")
        host.flag_broken_no_code_rulings([ruled_finding(NO_CODE_NOTES[3])], ["z/nit.py", "a/b.py"], [nit])
        self.assertEqual(host.no_code_broken, [{"issue": 1, "file": "a/b.py"}])

    def test_an_absolute_finding_path_names_the_changed_file(self):
        host = Host()
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."),
                    ruled_finding(NO_CODE_NOTES[1], "`/repo/a/b.py:3`")]
        host.flag_broken_no_code_rulings(findings, ["a/c.py", "a/b.py"])
        self.assertEqual(host.no_code_broken, [{"issue": 2, "file": "a/b.py"}])

    def test_a_run_without_a_no_code_ruling_flags_nothing(self):
        host = Host()
        host.flag_broken_no_code_rulings([parse_finding("`a/c.py:1` [bug] Proposed change: fix c.")], ["a/c.py"])
        self.assertEqual(host.no_code_broken, [])
        self.assertEqual(host.no_code_rulings, [])

    def test_the_packet_carries_the_flag_and_defaults_it_empty(self):
        flagged = review_loop_packet.packet_message({"no_code_ruling_broken": [{"issue": 2, "file": "a/b.py"}]})
        self.assertEqual(json.loads(flagged)["no_code_ruling_broken"], [{"issue": 2, "file": "a/b.py"}])
        self.assertNotIn("no_code_ruling_broken", json.loads(review_loop_packet.packet_message({})))

    def test_the_next_reviewer_prompt_lists_the_no_code_rulings(self):
        host = Host()
        finding = ruled_finding(NO_CODE_NOTES[3])
        host.flag_broken_no_code_rulings([finding], [])
        prompt = review_loop_prompts.reviewer_prompt(
            "/repo", "bug-reviewer", ["a/b.py"], [], no_code_rulings=tuple(host.no_code_rulings))
        plain = review_loop_prompts.reviewer_prompt("/repo", "bug-reviewer", ["a/b.py"], [])
        self.assertIn(review_loop_prompts.NO_CODE_REVIEW_RULE, prompt)
        self.assertNotIn(review_loop_prompts.NO_CODE_REVIEW_RULE, plain)
        self.assertIn("Make no code change.", prompt)

    def test_a_long_finding_keeps_its_ruling_note_in_the_reviewer_prompt(self):
        host = Host()
        long_change = "Proposed change: " + "add a guard. " * 60
        finding = parse_finding(ruled_change_text.changed_text(f"`a/b.py:3` [bug] {long_change}", NO_CODE_NOTES[1]))
        host.flag_broken_no_code_rulings([finding], [])
        prompt = review_loop_prompts.reviewer_prompt(
            "/repo", "bug-reviewer", ["a/b.py"], [], no_code_rulings=tuple(host.no_code_rulings))
        self.assertIn("add one Watch line to the change note", prompt)


if __name__ == "__main__":
    unittest.main()
