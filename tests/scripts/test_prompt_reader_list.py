"""Keeps changed_scope.PROMPT_READING_TESTS honest: a markdown-only change skips every test file outside it, so a test
that reads a skill or agent file must be listed or its prompt defect ships unseen."""
import importlib.util
import pathlib
import unittest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("changed_scope", TESTS_DIR.parent / "changed_scope.py")
changed_scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changed_scope)

# Read through bash and awk, which the signal cannot see.
LISTED_WITHOUT_SIGNAL = {"test_rule_anchors.py": "rule-anchors.sh reads the prompt files in awk"}


def files_with_signal():
    found = set()
    for test_file in TESTS_DIR.glob("test_*.py"):
        if test_file.name == pathlib.Path(__file__).name:
            continue
        if changed_scope.PROMPT_READER_SIGNAL.search(test_file.read_text()):
            found.add(test_file.name)
    return found


class PromptReaderListTest(unittest.TestCase):
    def test_every_test_file_that_reads_a_prompt_is_listed_or_excused(self):
        listed = set(changed_scope.PROMPT_READING_TESTS)
        excused = set(changed_scope.SIGNAL_BUT_NO_PROMPT_READ)
        unlisted = sorted(files_with_signal() - listed - excused)
        self.assertEqual(unlisted, [], "add each to PROMPT_READING_TESTS, or to SIGNAL_BUT_NO_PROMPT_READ with why")

    def test_a_listed_or_excused_file_that_stops_matching_is_removed(self):
        matching = files_with_signal()
        stale_listed = sorted(set(changed_scope.PROMPT_READING_TESTS) - matching - set(LISTED_WITHOUT_SIGNAL))
        stale_excused = sorted(set(changed_scope.SIGNAL_BUT_NO_PROMPT_READ) - matching)
        self.assertEqual(stale_listed + stale_excused, [], "these no longer match the prompt-reader signal")


if __name__ == "__main__":
    unittest.main()
